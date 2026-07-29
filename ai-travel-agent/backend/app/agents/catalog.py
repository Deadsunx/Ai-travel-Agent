"""Which models exist, and which ones this deployment can actually run.

Local models need Ollama on the same machine as the backend. That is true
in development and false on a hosted deployment, so availability is
something the server has to answer — the browser cannot know, and guessing
wrong means a request that hangs for ninety seconds against an endpoint
nobody is listening on.

The catalog lives here rather than in the frontend so both agree by
construction.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging
import time

import requests

from app.config import settings

logger = logging.getLogger(__name__)

CLOUD_PREFIX = "gemini"

#: How long a reachability answer is trusted. Long enough that a burst of
#: requests probes once, short enough that starting Ollama unlocks the local
#: models without restarting the backend.
PROBE_TTL_SECONDS = 30
PROBE_TIMEOUT_SECONDS = 2

LOCAL_UNAVAILABLE = (
    "Runs on your own machine. Clone the repo and start Ollama to use this model."
)
CLOUD_UNAVAILABLE = "No Google API key is configured on this server."


@dataclass(frozen=True)
class Model:
    value: str
    label: str
    kind: str      # "local" | "cloud"


CATALOG: List[Model] = [
    Model("gemini-flash-latest", "Gemini Flash", "cloud"),
    Model("gemini-flash-lite-latest", "Gemini Flash Lite", "cloud"),
    Model("qwen3.5:4b", "Qwen3.5 4B", "local"),
    Model("qwen3:8b", "Qwen3 8B", "local"),
    Model("qwen3.5:latest", "Qwen3.5 9B", "local"),
    Model("gemma2:9b", "Gemma2 9B", "local"),
]

_probe: Dict[str, Any] = {"checked_at": 0.0, "reachable": False}


def is_cloud(model_name: str) -> bool:
    return str(model_name or "").startswith(CLOUD_PREFIX)


def _ollama_root() -> Optional[str]:
    base = (settings.openai_api_base or "").rstrip("/")
    if not base.endswith("/v1"):
        return None
    return base[: -len("/v1")]


def ollama_reachable(force: bool = False) -> bool:
    """True when a local Ollama actually answers, not merely configured.

    Cached briefly: this is consulted on every model listing and every chat
    request, and a dead host costs a full connection timeout each time.
    """
    now = time.monotonic()
    if not force and now - _probe["checked_at"] < PROBE_TTL_SECONDS:
        return bool(_probe["reachable"])

    root = _ollama_root()
    reachable = False
    if root:
        try:
            response = requests.get(f"{root}/api/tags", timeout=PROBE_TIMEOUT_SECONDS)
            reachable = response.status_code == 200
        except Exception as e:
            logger.debug("Ollama not reachable at %s: %s", root, e)

    _probe.update({"checked_at": now, "reachable": reachable})
    return reachable


def available_models() -> List[Dict[str, Any]]:
    """The catalog, annotated with what this deployment can run and why not."""
    local_ok = ollama_reachable()
    cloud_ok = bool(settings.google_api_key)

    listed = []
    for model in CATALOG:
        ok = cloud_ok if model.kind == "cloud" else local_ok
        listed.append({
            "value": model.value,
            "label": model.label,
            "kind": model.kind,
            "available": ok,
            "reason": None if ok else (
                CLOUD_UNAVAILABLE if model.kind == "cloud" else LOCAL_UNAVAILABLE
            ),
        })
    return listed


def is_available(model_name: str) -> bool:
    """Can this deployment run the named model?"""
    if is_cloud(model_name):
        return bool(settings.google_api_key)
    return ollama_reachable()


def default_model() -> str:
    """The configured model when this deployment can run it, else the first
    one it can. Keeps a cloud-only deployment working without every client
    having to know it is cloud-only."""
    if settings.model_name and is_available(settings.model_name):
        return settings.model_name

    for model in available_models():
        if model["available"]:
            return model["value"]
    return settings.model_name
