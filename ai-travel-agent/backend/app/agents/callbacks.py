"""Streaming callbacks for the Travel Planning Agent"""

from typing import Any, Dict, List, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
import asyncio


class StreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming agent responses"""
    
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.current_tool = None
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs
    ) -> None:
        """Called when LLM starts generating"""
        pass
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called for each new token from the LLM"""
        asyncio.create_task(self.queue.put({
            "type": "token",
            "content": token
        }))
    
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Called when LLM finishes generating"""
        pass
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs
    ) -> None:
        """Called when a tool starts executing"""
        tool_name = serialized.get("name", "unknown")
        self.current_tool = tool_name
        
        # Map tool names to user-friendly messages
        tool_messages = {
            "google_search": "🔍 Searching for travel information...",
            "flight_search": "✈️ Finding available flights...",
            "hotel_search": "🏨 Searching for accommodations...",
            "restaurant_finder": "🍽️ Finding restaurants...",
            "budget_calculator": "💰 Calculating budget...",
            "itinerary_builder": "📅 Building your itinerary..."
        }
        
        message = tool_messages.get(tool_name, f"🔧 Using {tool_name}...")
        
        asyncio.create_task(self.queue.put({
            "type": "status",
            "message": message,
            "tool": tool_name
        }))
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """Called when a tool finishes executing"""
        tool_messages = {
            "google_search": "✅ Found travel information",
            "flight_search": "✅ Found flight options",
            "hotel_search": "✅ Found accommodation options",
            "restaurant_finder": "✅ Found restaurant recommendations",
            "budget_calculator": "✅ Budget calculated",
            "itinerary_builder": "✅ Itinerary built"
        }
        
        message = tool_messages.get(self.current_tool, "✅ Tool completed")
        
        asyncio.create_task(self.queue.put({
            "type": "status",
            "message": message,
            "tool": self.current_tool
        }))
        
        self.current_tool = None
    
    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Called when a tool errors"""
        asyncio.create_task(self.queue.put({
            "type": "error",
            "message": f"Tool error: {str(error)}",
            "tool": self.current_tool
        }))
        self.current_tool = None
    
    def on_agent_action(self, action, **kwargs) -> None:
        """Called when agent decides on an action"""
        pass
    
    def on_agent_finish(self, finish, **kwargs) -> None:
        """Called when agent finishes"""
        asyncio.create_task(self.queue.put({
            "type": "status",
            "message": "🎉 Trip plan ready!"
        }))


class AgentProgressHandler:
    """Simpler progress handler without async queue"""
    
    def __init__(self):
        self.steps = []
        self.current_step = None
    
    def add_step(self, step_type: str, message: str, tool: str = None):
        """Add a progress step"""
        step = {
            "type": step_type,
            "message": message,
            "tool": tool
        }
        self.steps.append(step)
        self.current_step = step
    
    def get_steps(self) -> List[dict]:
        """Get all recorded steps"""
        return self.steps
    
    def get_latest(self) -> Optional[dict]:
        """Get the latest step"""
        return self.current_step
