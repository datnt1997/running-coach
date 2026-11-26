import pytest

from app import config
from app.ai import factory


class _Anthropic:
    def __init__(self, model=None):
        self.model = model


class _Gemini:
    def __init__(self, model=None):
        self.model = model


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


def test_plan_edits_fall_back_to_the_chat_provider(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "anthropic")
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", "gemini")
    monkeypatch.setattr(config, "PLAN_EDIT_AI_PROVIDER", None)
    assert isinstance(factory.get_plan_edit_ai_client_dep(), _Gemini)


def test_only_plan_edits_can_be_routed_to_another_provider(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", "gemini")
    monkeypatch.setattr(config, "PLAN_EDIT_AI_PROVIDER", "anthropic")
    assert isinstance(factory.get_plan_edit_ai_client_dep(), _Anthropic)
    assert isinstance(factory.get_chat_ai_client_dep(), _Gemini)
    assert isinstance(factory.get_ai_client_dep(), _Gemini)


def test_each_role_can_name_its_own_model(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "gemini:gemini-4-neon")
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", "gemini:gemini-4-hydrogen")
    monkeypatch.setattr(config, "PLAN_EDIT_AI_PROVIDER", "anthropic:claude-x")
    assert factory.get_ai_client_dep().model == "gemini-4-neon"
    assert factory.get_chat_ai_client_dep().model == "gemini-4-hydrogen"
    edit = factory.get_plan_edit_ai_client_dep()
    assert isinstance(edit, _Anthropic) and edit.model == "claude-x"


def test_provider_without_model_uses_the_client_default(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", None)
    assert factory.get_chat_ai_client_dep().model is None


def test_validate_accepts_a_model_suffix(monkeypatch):
    _set(monkeypatch, "gemini:gemini-4-neon", "anthropic:claude-x", None, "g")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.validate_config()
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    config.validate_config()


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", "nope")
    with pytest.raises(ValueError):
        factory.get_chat_ai_client_dep()


def _set(monkeypatch, provider, chat, anthropic_key, gemini_key):
    monkeypatch.setattr(config, "AI_PROVIDER", provider)
    monkeypatch.setattr(config, "CHAT_AI_PROVIDER", chat)
    monkeypatch.setattr(config, "PLAN_EDIT_AI_PROVIDER", None)
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


def test_validate_plan_edit_provider_requires_its_key(monkeypatch):
    _set(monkeypatch, "gemini", "gemini", None, "g")
    monkeypatch.setattr(config, "PLAN_EDIT_AI_PROVIDER", "anthropic")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.validate_config()


def test_validate_both_missing_anthropic(monkeypatch):
    _set(monkeypatch, "anthropic", "gemini", None, "g")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.validate_config()


def test_anthropic_model_env(monkeypatch):
    monkeypatch.undo()  # drop the autouse fakes: this test needs the real AnthropicClient
    from app.ai.anthropic_client import AnthropicClient

    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-x")
    assert AnthropicClient(api_key="k").model == "claude-x"
    monkeypatch.delenv("ANTHROPIC_MODEL")
    assert AnthropicClient(api_key="k").model == "claude-sonnet-4-6"


def test_gemini_model_env(monkeypatch):
    pytest.importorskip("google.generativeai")
    monkeypatch.undo()  # drop the autouse fakes: this test needs the real GeminiClient
    from app.ai.gemini_client import GeminiClient

    monkeypatch.setenv("GEMINI_MODEL", "gemini-x")
    assert GeminiClient(api_key="k").model_name == "gemini-x"
    monkeypatch.delenv("GEMINI_MODEL")
    assert GeminiClient(api_key="k").model_name == "gemini-2.0-flash"
