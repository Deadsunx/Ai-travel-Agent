"""Direct client for Ollama's native /api/chat endpoint.

Used only for the parameter-extraction step. Extraction is a parsing job with
one right answer, so the reasoning pass that models like Qwen3.5 run by
default is pure latency. Ollama can switch it off with `think: false`, but
only on its native endpoint — the OpenAI-compatible /v1 route ignores the
flag. Measured on an RTX 4070 laptop with qwen3.5:4b:

    think on (default) : 69.7s, 2863 tokens
    think off          :  3.1s,  117 tokens

Same JSON either way, so the reasoning buys nothing here. The synthesis step
still goes through LangChain, which needs /v1 for streaming.
"""

import json
import logging
from typing import Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_TIMEOUT = 90
SYNTHESIS_TIMEOUT = 300


def _native_url() -> Optional[str]:
    """Turn the configured /v1 base URL into the native API root."""
    base = (settings.openai_api_base or "").rstrip("/")
    if not base.endswith("/v1"):
        return None
    return base[: -len("/v1")]


def is_available(model_name: str) -> bool:
    """Native calls only make sense for local Ollama models."""
    return bool(_native_url()) and not model_name.startswith("gemini")


def stream_without_thinking(model_name: str, prompt: str, queue) -> None:
    """Stream a reply with reasoning disabled, pushing chunks onto `queue`.

    Runs in a worker thread; `queue` is a plain queue.Queue drained by the
    event loop. A None sentinel marks the end, and an Exception instance
    signals failure so the caller can fall back.
    """
    root = _native_url()
    if not root:
        queue.put(RuntimeError("no native endpoint"))
        return

    try:
        with requests.post(
            f"{root}/api/chat",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "think": False,
                "options": {"temperature": 0.3, "num_ctx": 8192},
            },
            timeout=SYNTHESIS_TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    queue.put(piece)
                if chunk.get("done"):
                    break
        queue.put(None)
    except Exception as e:
        logger.warning("Native Ollama streaming failed (%s); falling back", e)
        queue.put(e)


def complete_without_thinking(model_name: str, prompt: str) -> Optional[str]:
    """Return the model's reply with reasoning disabled, or None on failure."""
    root = _native_url()
    if not root:
        return None

    try:
        response = requests.post(
            f"{root}/api/chat",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_ctx": 8192},
            },
            timeout=EXTRACTION_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "") or None
    except Exception as e:
        logger.warning("Native Ollama extraction failed (%s); falling back", e)
        return None
