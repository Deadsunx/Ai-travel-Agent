"""Which models a deployment offers, and what it does with one it cannot run.

The hosted deployment has no Ollama. Getting this wrong does not fail
loudly — it waits out a connection timeout on every request — so the rules
are pinned here.
"""

import pytest

from app.agents import catalog
from app.config import settings


@pytest.fixture
def local_runtime(monkeypatch):
    """Pretend Ollama is up, without touching the network."""
    monkeypatch.setattr(catalog, "ollama_reachable", lambda force=False: True)
    monkeypatch.setattr(settings, "google_api_key", "test-key")


@pytest.fixture
def cloud_only(monkeypatch):
    """A hosted deployment: a Gemini key, and no Ollama anywhere."""
    monkeypatch.setattr(catalog, "ollama_reachable", lambda force=False: False)
    monkeypatch.setattr(settings, "google_api_key", "test-key")


def test_local_models_are_locked_without_ollama(cloud_only):
    listed = {m["value"]: m for m in catalog.available_models()}

    assert listed["qwen3:8b"]["available"] is False
    assert "own machine" in listed["qwen3:8b"]["reason"]
    assert listed["gemini-flash-latest"]["available"] is True
    assert listed["gemini-flash-latest"]["reason"] is None


def test_local_models_unlock_when_ollama_answers(local_runtime):
    listed = {m["value"]: m for m in catalog.available_models()}

    assert listed["qwen3:8b"]["available"] is True
    assert all(m["available"] for m in catalog.available_models())


def test_cloud_models_are_locked_without_a_key(monkeypatch):
    monkeypatch.setattr(catalog, "ollama_reachable", lambda force=False: True)
    monkeypatch.setattr(settings, "google_api_key", "")

    listed = {m["value"]: m for m in catalog.available_models()}
    assert listed["gemini-flash-latest"]["available"] is False
    assert "API key" in listed["gemini-flash-latest"]["reason"]


def test_a_configured_model_it_cannot_run_falls_back(cloud_only, monkeypatch):
    """A hosted deploy left on the local default must still work."""
    monkeypatch.setattr(settings, "model_name", "qwen3:8b")
    assert catalog.default_model() == "gemini-flash-latest"


def test_the_configured_model_wins_when_runnable(local_runtime, monkeypatch):
    monkeypatch.setattr(settings, "model_name", "qwen3:8b")
    assert catalog.default_model() == "qwen3:8b"


def test_an_unconfigured_ollama_is_never_probed(monkeypatch):
    """Without a /v1 base URL there is nothing to probe, and probing a host
    that is not there is what makes a request hang."""
    monkeypatch.setattr(settings, "openai_api_base", "")
    catalog._probe["checked_at"] = 0

    def explode(*args, **kwargs):
        raise AssertionError("should not have made a request")

    monkeypatch.setattr(catalog.requests, "get", explode)
    assert catalog.ollama_reachable(force=True) is False


def test_reachability_is_cached_between_calls(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_base", "http://ollama.test/v1")
    calls = []

    class Response:
        status_code = 200

    monkeypatch.setattr(catalog.requests, "get",
                        lambda *a, **k: calls.append(1) or Response())

    catalog._probe["checked_at"] = 0
    assert catalog.ollama_reachable(force=True) is True
    catalog.ollama_reachable()
    catalog.ollama_reachable()

    assert len(calls) == 1, "a dead host must not cost a timeout per request"
