import pytest

from app import config
from app.ai import factory


class _Anthropic:
    pass


class _Gemini:
    pass


@pytest.fixture(autouse=True)
def fake_clients(monkeypatch):
    import app.ai.anthropic_client as a
    import app.ai.gemini_client as g

    monkeypatch.setattr(a, "AnthropicClient", _Anthropic)
    monkeypatch.setattr(g, "GeminiClient", _Gemini, raising=False)


def test_chat_falls_back_to_ai_provider(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", None)
    assert isinstance(factory.get_chat_ai_client_dep(), _Anthropic)


def test_chat_honors_chat_provider(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", "gemini")
    assert isinstance(factory.get_chat_ai_client_dep(), _Gemini)
    assert isinstance(factory.get_ai_client_dep(), _Anthropic)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", "nope")
    with pytest.raises(ValueError):
        factory.get_chat_ai_client_dep()


def _set(monkeypatch, provider, chat, anthropic_key, gemini_key):
    monkeypatch.setattr(config, "AI_PROVIDER", provider)
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", chat)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", anthropic_key)
    monkeypatch.setattr(config, "GEMINI_API_KEY", gemini_key)
    for n in ("DATABASE_URL", "STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET",
              "STRAVA_WEBHOOK_VERIFY_TOKEN", "STRAVA_REDIRECT_URI"):
        monkeypatch.setattr(config, n, "x")


def test_validate_anthropic_only(monkeypatch):
    _set(monkeypatch, "anthropic", None, "k", None)
    config.validate_config()


def test_validate_gemini_chat_requires_key(monkeypatch):
    _set(monkeypatch, "anthropic", "gemini", "k", None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        config.validate_config()
    monkeypatch.setattr(config, "GEMINI_API_KEY", "g")
    config.validate_config()


def test_validate_both_missing_anthropic(monkeypatch):
    _set(monkeypatch, "anthropic", "gemini", None, "g")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.validate_config()


def test_gemini_model_env(monkeypatch):
    pytest.importorskip("google.generativeai")
    from app.ai.gemini_client import GeminiClient

    monkeypatch.setenv("GEMINI_MODEL", "gemini-x")
    assert GeminiClient(api_key="k").model_name == "gemini-x"
    monkeypatch.delenv("GEMINI_MODEL")
    assert GeminiClient(api_key="k").model_name == "gemini-2.0-flash"
