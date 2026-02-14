import redis
import json
import os
from typing import Optional, Any
from app.config import settings


class RedisService:
    """Redis service for caching and session management"""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            try:
                self._client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True
                )
                # Test connection
                self._client.ping()
            except Exception as e:
                print(f"Redis connection error: {e}")
                self._client = None
    
    @property
    def client(self):
        return self._client
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        try:
            if self._client:
                self._client.ping()
                return True
        except:
            pass
        return False
    
    def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        try:
            if self._client:
                return self._client.get(key)
        except Exception as e:
            print(f"Redis GET error: {e}")
        return None
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value in Redis with optional expiry"""
        try:
            if self._client:
                return self._client.set(key, value, ex=ex)
        except Exception as e:
            print(f"Redis SET error: {e}")
        return False
    
    def setex(self, key: str, time: int, value: str) -> bool:
        """Set value with expiry time in seconds"""
        try:
            if self._client:
                return self._client.setex(key, time, value)
        except Exception as e:
            print(f"Redis SETEX error: {e}")
        return False
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            if self._client:
                return self._client.delete(key) > 0
        except Exception as e:
            print(f"Redis DELETE error: {e}")
        return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            if self._client:
                return self._client.exists(key) > 0
        except Exception as e:
            print(f"Redis EXISTS error: {e}")
        return False
    
    def incr(self, key: str) -> int:
        """Increment key value"""
        try:
            if self._client:
                return self._client.incr(key)
        except Exception as e:
            print(f"Redis INCR error: {e}")
        return 0
    
    def expire(self, key: str, time: int) -> bool:
        """Set expiry on key"""
        try:
            if self._client:
                return self._client.expire(key, time)
        except Exception as e:
            print(f"Redis EXPIRE error: {e}")
        return False
    
    # ============== Session Management ==============
    
    def save_session(self, session_id: str, messages: list, ttl: int = 86400) -> bool:
        """Save chat session to Redis (24h default TTL)"""
        key = f"session:{session_id}"
        return self.setex(key, ttl, json.dumps(messages))
    
    def get_session(self, session_id: str) -> Optional[list]:
        """Get chat session from Redis"""
        key = f"session:{session_id}"
        data = self.get(key)
        return json.loads(data) if data else None
    
    def append_message(self, session_id: str, message: dict, ttl: int = 86400) -> bool:
        """Append a message to session"""
        messages = self.get_session(session_id) or []
        messages.append(message)
        return self.save_session(session_id, messages, ttl)
    
    # ============== Rate Limiting ==============
    
    def check_rate_limit(self, user_id: str, max_requests: int = 10, window: int = 3600) -> bool:
        """
        Check if user has exceeded rate limit
        Returns True if request is allowed, False if rate limited
        """
        key = f"ratelimit:{user_id}"
        requests = self.incr(key)
        
        if requests == 1:
            self.expire(key, window)
        
        return requests <= max_requests
    
    def get_remaining_requests(self, user_id: str, max_requests: int = 10) -> int:
        """Get remaining requests for user"""
        key = f"ratelimit:{user_id}"
        count_str = self.get(key)
        count = int(count_str) if count_str else 0
        return max(0, max_requests - count)
    
    # ============== Cache Management ==============
    
    def get_cached(self, cache_key: str) -> Optional[dict]:
        """Get cached result"""
        data = self.get(cache_key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_cache(self, cache_key: str, data: dict, ttl: int = 3600) -> bool:
        """Set cached result with TTL"""
        return self.setex(cache_key, ttl, json.dumps(data))


# Singleton instance
redis_service = RedisService()
