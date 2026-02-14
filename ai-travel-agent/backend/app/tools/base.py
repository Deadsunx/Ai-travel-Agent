from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, Any
import json

from app.services.redis_service import redis_service


class BaseTravelTool(BaseTool):
    """Base class for all travel-related tools with Redis caching"""
    
    def _get_cached_result(self, cache_key: str) -> Optional[dict]:
        """Check Redis cache before making API call"""
        return redis_service.get_cached(cache_key)
    
    def _set_cache(self, cache_key: str, data: Any, ttl: int = 3600) -> bool:
        """Store result in Redis with TTL"""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {"result": data}
        return redis_service.set_cache(cache_key, data, ttl)
    
    def _format_error(self, error: str) -> str:
        """Format error message as JSON"""
        return json.dumps({"error": error, "success": False})
    
    def _format_result(self, data: Any) -> str:
        """Format successful result as JSON"""
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False)
