"""What this deployment can run.

The browser asks; the server answers. A hosted deployment has no Ollama, so
its local models come back locked with the reason why, and the picker can
show that instead of offering a model the request would hang on.
"""

from fastapi import APIRouter

from app.agents.catalog import available_models, default_model, ollama_reachable

router = APIRouter()


@router.get("/")
async def list_models():
    models = available_models()
    return {
        "models": models,
        "default": default_model(),
        "local_runtime": "ollama" if ollama_reachable() else None,
    }
