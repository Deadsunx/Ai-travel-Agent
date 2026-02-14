from pydantic import BaseModel, Field
from typing import Type
import requests
import json

from app.tools.base import BaseTravelTool
from app.config import settings


class GoogleSearchInput(BaseModel):
    """Input schema for Google Search tool"""
    query: str = Field(description="Search query for Google")
    num_results: int = Field(default=5, description="Number of results to return (1-10)")


class GoogleSearchTool(BaseTravelTool):
    """Tool for searching the web using SerpAPI"""
    
    name: str = "google_search"
    description: str = """Useful for searching the web for current information about 
    destinations, attractions, reviews, travel tips, and general travel information. 
    Input should be a search query string. Returns relevant web results with titles, 
    links, and snippets."""
    args_schema: Type[BaseModel] = GoogleSearchInput
    
    def _run(self, query: str, num_results: int = 5) -> str:
        """Execute Google search using SerpAPI"""
        
        # Limit results
        num_results = min(max(1, num_results), 10)
        
        # Check cache first (1 hour TTL)
        cache_key = f"google_search:{query}:{num_results}"
        cached = self._get_cached_result(cache_key)
        if cached:
            return self._format_result(cached)
        
        try:
            # SerpAPI request
            params = {
                "q": query,
                "api_key": settings.serpapi_key,
                "num": num_results,
                "engine": "google"
            }
            
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Extract organic results
            for result in data.get("organic_results", [])[:num_results]:
                results.append({
                    "title": result.get("title"),
                    "link": result.get("link"),
                    "snippet": result.get("snippet"),
                    "position": result.get("position")
                })
            
            # Add knowledge graph if available
            if "knowledge_graph" in data:
                kg = data["knowledge_graph"]
                results.insert(0, {
                    "type": "knowledge_graph",
                    "title": kg.get("title"),
                    "description": kg.get("description"),
                    "source": kg.get("source", {}).get("link")
                })
            
            # Cache for 1 hour
            self._set_cache(cache_key, results, ttl=3600)
            
            return self._format_result(results)
            
        except requests.exceptions.Timeout:
            return self._format_error("Search request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            return self._format_error(f"Search request failed: {str(e)}")
        except Exception as e:
            return self._format_error(f"Search failed: {str(e)}")
    
    async def _arun(self, query: str, num_results: int = 5) -> str:
        """Async version - delegates to sync for now"""
        return self._run(query, num_results)
