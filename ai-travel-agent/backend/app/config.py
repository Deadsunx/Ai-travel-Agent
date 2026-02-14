from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database
    database_url: str = "postgresql://postgres:postgres123@localhost:5432/travel_agent"
    
    # Redis
    redis_url: str = "redis://:redis123@localhost:6379/0"
    
    # LLM APIs
    openai_api_key: str = "ollama"
    openai_api_base: str = "http://host.docker.internal:11434/v1"
    model_name: str = "qwen3:8b"
    available_models: list = ["qwen3:8b", "gemma2:9b", "gemini-2.0-flash"]
    google_api_key: str = ""
    
    # External APIs
    serpapi_key: str = ""
    rapidapi_key: str = ""
    foursquare_api_key: str = ""
    
    # Application
    secret_key: str = "your-secret-key"
    environment: str = "development"
    log_level: str = "INFO"
    
    # Agent Settings
    max_agent_iterations: int = 15
    agent_timeout: int = 120  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
