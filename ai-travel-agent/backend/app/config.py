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
    available_models: list = [
        "qwen3.5:4b", "qwen3:8b", "qwen3.5:latest", "gemma2:9b",
        # Version-pinned Gemini names are closed to new keys; use the aliases.
        "gemini-flash-latest", "gemini-flash-lite-latest",
    ]
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
    agent_timeout: int = 120  # seconds, per LLM call (extraction step)

    # Planner selection: "graph" is the multi-agent LangGraph orchestrator,
    # "pipeline" the older single-pass one. Per-request override:
    # ChatRequest.planner.
    #
    # The graph is the default because it wins the golden-query comparison
    # 15/16 to 13/16 — it fixes both duplicate-restaurant cases and holds a
    # plan to its budget. It costs roughly 17% more latency; PLANNER=pipeline
    # buys that back.
    planner: str = "graph"
    # Revision rounds the critic may request before the plan is delivered
    # as-is. Local 8B models are slow, so 1 is the default; 2 is reasonable
    # on Gemini. Hard-capped by MAX_REVISIONS_CEILING in the critic.
    max_revisions: int = 1
    # Model for the LLM critic pass; empty = use the request's main model.
    critic_model: str = ""
    # The advisory (LLM) half of the critic. Off by default: it costs a
    # whole extra call per plan and the deterministic rules are what
    # actually drive revisions.
    critic_advisory_pass: bool = False
    # Write a plan_runs row per planning run. Turned off in tests so a unit
    # run leaves no trace in the comparison data.
    record_plan_runs: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
