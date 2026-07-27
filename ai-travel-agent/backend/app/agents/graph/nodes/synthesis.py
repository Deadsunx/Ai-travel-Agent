"""Synthesis node: write the answer and stream it to the client.

Reuses the v1 agent's `stream_llm` (native Ollama streaming with the
LangChain fallback, plus <think>-block filtering) so both planners produce
identically formatted output and only the *content* differs.
"""

from typing import Any, Dict
import json

from app.agents.graph.runtime import emit, runtime_of, status
from app.agents.graph.state import PlanState, empty_collected, to_collected
from app.agents.prompts import get_chat_prompt, get_synthesis_prompt

#: Redis-stored plans can be large; the chat prompt only needs the gist.
PLAN_CONTEXT_CHARS = 6000


async def synthesis(state: PlanState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Stream the final answer, then hand back the text and collected data."""
    agent = runtime_of(config).agent
    user_query = state["user_query"]

    if state.get("intent") == "plan_trip":
        await status(config, "📝 Writing your itinerary...")
        collected = to_collected(state)
        prompt = get_synthesis_prompt(
            user_query,
            json.dumps(collected, ensure_ascii=False, default=str),
            agent.has_mock_data(collected),
        )
    else:
        stored = agent.load_stored_plan()
        plan_context = (
            json.dumps(stored, ensure_ascii=False, default=str)[:PLAN_CONTEXT_CHARS]
            if stored else ""
        )
        collected = stored or empty_collected()
        prompt = get_chat_prompt(user_query, agent.history_text(), plan_context)

    final_text = ""
    async for event in agent.stream_llm(prompt):
        if event["type"] == "text":
            final_text = event["content"]
        else:
            await emit(config, event)

    return {"final_text": final_text, "collected_data": collected}
