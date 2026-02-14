"""Main Travel Planning Agent using LangChain ReAct with Local Ollama + Gemini"""

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationSummaryBufferMemory
from typing import Optional, Dict, Any, List
import json
import asyncio

from app.config import settings
from app.tools import get_all_tools
from app.agents.prompts import TRAVEL_AGENT_SYSTEM_PROMPT, REACT_PROMPT_TEMPLATE
from app.services.redis_service import redis_service

# Gemini models use a different provider
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]


def get_local_llm(model_name: str = settings.model_name) -> ChatOpenAI:
    """
    Returns a configured ChatOpenAI instance pointing to local Ollama.
    """
    return ChatOpenAI(
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key,
        model=model_name,
        temperature=0.3,
        max_tokens=4096,
        streaming=True,
        tiktoken_model_name="gpt-3.5-turbo"
    )


def get_gemini_llm(model_name: str = "gemini-2.0-flash"):
    """
    Returns a configured ChatGoogleGenerativeAI instance for Gemini.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=0.3,
        max_output_tokens=4096,
        streaming=True,
    )


def get_llm(model_name: str = settings.model_name):
    """
    Router: returns the correct LLM based on model name.
    Gemini models use Google API, others use local Ollama.
    """
    if any(model_name.startswith(g) for g in GEMINI_MODELS):
        return get_gemini_llm(model_name)
    return get_local_llm(model_name)


class TravelPlanningAgent:
    """Travel planning agent using LangChain ReAct pattern"""
    
    def __init__(self, session_id: str, model_name: str = settings.model_name):
        self.session_id = session_id
        self.model_name = model_name
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize LangChain ReAct Agent with local LLM"""
        
        # Initialize LLM
        self.llm = get_llm(self.model_name)
        
        # Initialize tools
        self.tools = get_all_tools()
        
        # Memory for conversation history - Upgraded to SummaryBuffer
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            memory_key="chat_history",
            return_messages=True,
            max_token_limit=2000  # Summarize if context exceeds 2000 tokens
        )
        
        # Load existing conversation from Redis
        self._load_conversation_history()
        
        # ReAct prompt template
        react_prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
        
        # Create ReAct agent (text-based tool calling)
        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=react_prompt
        )
        
        # Initialize LLM with stop sequences to enforce ReAct format
        self.llm = self.llm.bind(stop=["\nObservation:"])

        # Create executor with error handling
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=False,               # Disabled to prevent callback errors
            max_iterations=25,           # Increased to 25
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    def _load_conversation_history(self) -> List[Dict]:
        """Load conversation history from Redis"""
        try:
            messages = redis_service.get_session(self.session_id)
            if messages:
                for msg in messages:
                    if msg.get("role") == "user":
                        self.memory.chat_memory.add_user_message(msg.get("content", ""))
                    elif msg.get("role") == "assistant":
                        self.memory.chat_memory.add_ai_message(msg.get("content", ""))
            return messages if messages else []
        except Exception as e:
            print(f"Error loading conversation history: {e}")
            return []
    
    def _save_conversation(self, user_input: str, agent_output: str):
        """Save conversation to Redis"""
        try:
            messages = redis_service.get_session(self.session_id) or []
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": agent_output})
            redis_service.save_session(self.session_id, messages)
        except Exception as e:
            print(f"Error saving conversation: {e}")
    
    async def plan_trip(self, user_query: str) -> Dict[str, Any]:
        """Main method to process trip planning request"""
        try:
            collected_data = {
                "flights": None,
                "hotels": None,
                "restaurants": None,
                "budget": None,
                "itinerary": None,
                "search_results": []
            }
            
            # Invoke the agent
            result = await self.executor.ainvoke({"input": user_query})
            
            # Extract tool outputs from intermediate steps
            if "intermediate_steps" in result:
                for step in result["intermediate_steps"]:
                    action, output = step
                    
                    try:
                        # Parse JSON output if possible
                        if isinstance(output, str):
                            # Clean potential markdown code blocks
                            clean_output = output
                            if "```json" in clean_output:
                                clean_output = clean_output.split("```json")[1].split("```")[0].strip()
                            elif "```" in clean_output:
                                clean_output = clean_output.split("```")[1].split("```")[0].strip()
                                
                            data = json.loads(clean_output)
                        else:
                            data = output
                            
                        # Map to collected_data keys
                        if action.tool == "flight_search":
                            collected_data["flights"] = data
                        elif action.tool == "hotel_search":
                            collected_data["hotels"] = data
                        elif action.tool == "restaurant_finder":
                            collected_data["restaurants"] = data
                        elif action.tool == "itinerary_builder":
                            collected_data["itinerary"] = data
                        elif action.tool == "budget_calculator":
                            collected_data["budget"] = data
                            
                    except Exception as e:
                        print(f"Error parsing tool output for {action.tool}: {e}")
                        continue
            
            final_response = result.get("output", "")
            
            # Fallback if empty response
            if not final_response or len(final_response) < 20:
                 final_response = "I processed your request but couldn't generate a complete valid response. Please try again or provide more details."

            # Save conversation
            self._save_conversation(user_query, final_response)
            
            return {
                "success": True,
                "response": final_response,
                "collected_data": collected_data,
                "session_id": self.session_id
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"Agent error: {error_msg}")
            
            fallback = f"""I encountered an error while processing your request: {error_msg}.
            
Please try again later or rephrase your request."""
            
            return {
                "success": False,
                "error": error_msg,
                "response": fallback,
                "session_id": self.session_id
            }
    
    def sync_plan_trip(self, user_query: str) -> Dict[str, Any]:
        """Synchronous version of plan_trip"""
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.plan_trip(user_query))
                    return future.result()
            else:
                return loop.run_until_complete(self.plan_trip(user_query))
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"Error: {str(e)}",
                "session_id": self.session_id
            }


def create_agent(session_id: str, model_name: str = settings.model_name) -> TravelPlanningAgent:
    """Factory function to create a travel planning agent"""
    return TravelPlanningAgent(session_id, model_name)
