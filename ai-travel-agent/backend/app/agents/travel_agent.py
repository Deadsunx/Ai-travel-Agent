"""Travel Planning Agent — deterministic pipeline + LLM synthesis.

Architecture (replaces the old forced-ReAct loop):
  1. One structured-output LLM call extracts trip parameters from the message.
  2. Flights / hotels / restaurants are fetched in PARALLEL (plain function
     calls — no agent loop, so tool coverage is 100% and latency is bounded).
  3. Budget is computed from the real prices found; the itinerary skeleton is
     grounded in the real restaurant names.
  4. One streaming LLM call writes the final answer from the collected data.

For refinements/chit-chat (no new destination), a single conversational LLM
call is made using the stored plan as context.
"""

from langchain_openai import ChatOpenAI
from typing import Any, AsyncIterator, Dict, List, Optional
import asyncio
import json
import logging

from app.config import settings
from app.agents.streaming import ThinkFilter, strip_think
from app.agents.params import resolve_trip_params
from app.tools import (
    flight_search,
    hotel_search,
    restaurant_finder,
    budget_calculator,
    itinerary_builder,
    _extract_json_payload,
)
from app.agents.prompts import get_extraction_prompt, get_synthesis_prompt, get_chat_prompt
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

# Gemini models use a different provider
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

HISTORY_TURNS_IN_PROMPT = 6


def get_local_llm(model_name: str = settings.model_name) -> ChatOpenAI:
    """Configured ChatOpenAI instance pointing to local Ollama."""
    return ChatOpenAI(
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key,
        model=model_name,
        temperature=0.3,
        max_tokens=4096,
    )


def get_gemini_llm(model_name: str = "gemini-2.0-flash"):
    """Configured ChatGoogleGenerativeAI instance for Gemini."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=0.3,
        max_output_tokens=4096,
    )


def get_llm(model_name: str = settings.model_name):
    """Router: Gemini models use the Google API, others use local Ollama."""
    if any(model_name.startswith(g) for g in GEMINI_MODELS):
        return get_gemini_llm(model_name)
    return get_local_llm(model_name)


class TravelPlanningAgent:
    """Deterministic travel-planning pipeline with LLM extraction + synthesis."""

    def __init__(self, session_id: str, model_name: str = settings.model_name):
        self.session_id = session_id
        self.model_name = model_name
        self.llm = get_llm(model_name)

    # ------------------------------------------------------------------
    # Conversation history (Redis)
    # ------------------------------------------------------------------

    def _history(self) -> List[Dict]:
        try:
            return redis_service.get_session(self.session_id) or []
        except Exception as e:
            logger.warning("Error loading conversation history: %s", e)
            return []

    def _history_text(self) -> str:
        lines = []
        for msg in self._history()[-HISTORY_TURNS_IN_PROMPT:]:
            role = msg.get("role", "user").capitalize()
            content = str(msg.get("content", ""))[:600]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _save_conversation(self, user_input: str, agent_output: str):
        try:
            messages = self._history()
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": agent_output})
            redis_service.save_session(self.session_id, messages)
        except Exception as e:
            logger.warning("Error saving conversation: %s", e)

    def _load_stored_plan(self) -> Optional[Dict]:
        return redis_service.get_cached(f"plan:{self.session_id}")

    def _store_plan(self, collected_data: Dict):
        try:
            redis_service.set_cache(f"plan:{self.session_id}", collected_data, ttl=86400)
        except Exception as e:
            logger.warning("Error storing plan: %s", e)

    # ------------------------------------------------------------------
    # Step 1: parameter extraction
    # ------------------------------------------------------------------

    async def _extract_params(self, user_query: str) -> Dict[str, Any]:
        prompt = get_extraction_prompt(user_query, self._history_text())
        try:
            response = await asyncio.wait_for(self.llm.ainvoke(prompt), timeout=settings.agent_timeout)
            raw = strip_think(response.content if hasattr(response, "content") else str(response))
            params = _extract_json_payload(raw) or {}
        except Exception as e:
            logger.warning("Param extraction failed (%s); falling back to chat intent", e)
            params = {}

        if not isinstance(params, dict):
            params = {}
        params.setdefault("intent", "plan_trip" if params.get("destination") else "chat")
        if params.get("destination") is None and params["intent"] == "plan_trip":
            params["intent"] = "chat"
        return resolve_trip_params(params)

    # ------------------------------------------------------------------
    # Step 2: parallel data collection
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_load(raw: Optional[str]) -> Optional[Dict]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def _collect_data(self, params: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Run the data tools; yields progress events, then a final
        {"type": "collected", "data": ...} event."""
        destination = str(params["destination"])
        origin = str(params.get("origin") or "Delhi")
        collected: Dict[str, Any] = {
            "flights": None,
            "hotels": None,
            "restaurants": None,
            "budget": None,
            "itinerary": None,
            "search_results": [],
            "trip_params": params,
        }

        async def _named(name, func, /, **kwargs):
            try:
                return name, self._safe_load(await asyncio.to_thread(func, **kwargs))
            except Exception as e:
                logger.warning("%s failed: %s", name, e)
                return name, None

        tasks = [
            _named("flights", flight_search, origin=origin, destination=destination,
                   date=params["start_date"], return_date=params["end_date"],
                   passengers=params["travelers"]),
            _named("hotels", hotel_search, city=destination,
                   check_in=params["start_date"], check_out=params["end_date"],
                   guests=params["travelers"]),
            _named("restaurants", restaurant_finder, city=destination,
                   cuisine=params.get("cuisine"), budget="medium"),
        ]

        labels = {"flights": "✈️ Flights", "hotels": "🏨 Hotels", "restaurants": "🍽️ Restaurants"}
        for future in asyncio.as_completed(tasks):
            name, data = await future
            collected[name] = data
            count = len(data.get(name) or []) if isinstance(data, dict) else 0
            source = data.get("source", "") if isinstance(data, dict) else ""
            note = " (estimated)" if source.startswith("Mock") else ""
            yield {"type": "status", "message": f"{labels[name]}: found {count} options{note}"}

        # Budget from the real prices found
        def _cheapest(section: Optional[Dict], list_key: str, price_key: str) -> float:
            items = (section or {}).get(list_key) or []
            prices = []
            for item in items:
                try:
                    p = float(item.get(price_key, 0))
                    if p > 0:
                        prices.append(p)
                except (ValueError, TypeError):
                    continue
            return min(prices) if prices else 0

        collected["budget"] = self._safe_load(await asyncio.to_thread(
            budget_calculator,
            destination=destination,
            days=params["days"],
            travelers=params["travelers"],
            budget_limit=params["budget_limit"],
            flight_cost=_cheapest(collected["flights"], "flights", "price"),
            hotel_cost_per_night=_cheapest(collected["hotels"], "hotels", "price_per_night"),
        ))

        # Itinerary skeleton grounded in the real restaurant names
        restaurant_names = [
            r.get("name") for r in ((collected["restaurants"] or {}).get("restaurants") or [])
        ]
        collected["itinerary"] = self._safe_load(await asyncio.to_thread(
            itinerary_builder,
            destination=destination,
            days=params["days"],
            interests=params.get("interests"),
            restaurants=restaurant_names,
        ))

        yield {"type": "collected", "data": collected}

    # ------------------------------------------------------------------
    # Step 3: streaming synthesis
    # ------------------------------------------------------------------

    async def _stream_llm(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream an LLM response as token events, then a final 'text' event."""
        think_filter = ThinkFilter()
        full = ""
        async for chunk in self.llm.astream(prompt):
            piece = chunk.content if hasattr(chunk, "content") else str(chunk)
            if not piece:
                continue
            visible = think_filter.feed(piece)
            if visible:
                full += visible
                yield {"type": "token", "content": visible}
        tail = think_filter.flush()
        if tail:
            full += tail
            yield {"type": "token", "content": tail}
        yield {"type": "text", "content": full.strip()}

    @staticmethod
    def _has_mock_data(collected: Dict[str, Any]) -> bool:
        for section in ("flights", "hotels", "restaurants"):
            data = collected.get(section)
            if isinstance(data, dict) and str(data.get("source", "")).startswith("Mock"):
                return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def plan_trip_events(self, user_query: str) -> AsyncIterator[Dict[str, Any]]:
        """Full pipeline as an async event stream.

        Yields {"type": "status"|"token"|"result"|"error", ...} dicts; the
        "result" payload matches the old plan_trip() return shape.
        """
        try:
            yield {"type": "status", "message": "🔍 Understanding your travel request..."}
            params = await self._extract_params(user_query)

            if params["intent"] == "plan_trip" and params.get("destination"):
                yield {"type": "status",
                       "message": f"🌍 Planning {params['days']} days in {params['destination']} — searching live data..."}

                collected = None
                async for event in self._collect_data(params):
                    if event["type"] == "collected":
                        collected = event["data"]
                    else:
                        yield event

                yield {"type": "status", "message": "📝 Writing your itinerary..."}
                prompt = get_synthesis_prompt(
                    user_query,
                    json.dumps(collected, ensure_ascii=False, default=str),
                    self._has_mock_data(collected),
                )
            else:
                stored = self._load_stored_plan()
                plan_context = json.dumps(stored, ensure_ascii=False, default=str)[:6000] if stored else ""
                collected = stored or {
                    "flights": None, "hotels": None, "restaurants": None,
                    "budget": None, "itinerary": None, "search_results": [],
                }
                prompt = get_chat_prompt(user_query, self._history_text(), plan_context)

            final_text = ""
            async for event in self._stream_llm(prompt):
                if event["type"] == "text":
                    final_text = event["content"]
                else:
                    yield event

            if not final_text or len(final_text) < 20:
                final_text = ("I processed your request but couldn't generate a complete response. "
                              "Please try again or provide more details.")

            if params["intent"] == "plan_trip" and params.get("destination"):
                self._store_plan(collected)
            self._save_conversation(user_query, final_text)

            yield {
                "type": "result",
                "data": {
                    "success": True,
                    "response": final_text,
                    "collected_data": collected,
                    "session_id": self.session_id,
                },
            }

        except Exception as e:
            logger.exception("Agent pipeline error")
            yield {
                "type": "result",
                "data": {
                    "success": False,
                    "error": str(e),
                    "response": f"I encountered an error while processing your request: {e}. "
                                "Please try again or rephrase your request.",
                    "session_id": self.session_id,
                },
            }

    async def plan_trip(self, user_query: str) -> Dict[str, Any]:
        """Non-streaming entry point; same return shape as before."""
        result: Dict[str, Any] = {
            "success": False,
            "response": "No response generated.",
            "session_id": self.session_id,
        }
        async for event in self.plan_trip_events(user_query):
            if event["type"] == "result":
                result = event["data"]
        return result

    def sync_plan_trip(self, user_query: str) -> Dict[str, Any]:
        """Synchronous wrapper around plan_trip."""
        try:
            return asyncio.run(self.plan_trip(user_query))
        except RuntimeError:
            # Already inside an event loop — run in a worker thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.plan_trip(user_query)).result()
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"Error: {e}",
                "session_id": self.session_id,
            }


def create_agent(session_id: str, model_name: str = settings.model_name) -> TravelPlanningAgent:
    """Factory function to create a travel planning agent"""
    return TravelPlanningAgent(session_id, model_name)
