from app import config
from app.ai.client import AIClient


def get_ai_client(provider: str | None = None) -> AIClient:
    """Build a client from a provider setting: ``"gemini"`` or ``"gemini:<model>"``.

    Without a model, the client uses its own default (GEMINI_MODEL / ANTHROPIC_MODEL).
    """
    provider, _, model = (provider or config.AI_PROVIDER).partition(":")
    if provider == "anthropic":
        from app.ai.anthropic_client import AnthropicClient

        return AnthropicClient(model=model or None)
    elif provider == "gemini":
        from app.ai.gemini_client import GeminiClient

        return GeminiClient(model=model or None)
    raise ValueError(f"Unknown AI provider: {provider}")


def get_chat_ai_client() -> AIClient:
    """Client for the fitness chat; CHAT_AI_PROVIDER falls back to AI_PROVIDER."""
    return get_ai_client(config.CHAT_AI_PROVIDER or config.AI_PROVIDER)


def get_plan_edit_ai_client() -> AIClient:
    """Client for the Plan chat's edit step only, so edits can run on a stronger model than the chat.

    PLAN_EDIT_AI_PROVIDER falls back to CHAT_AI_PROVIDER, then AI_PROVIDER.
    """
    return get_ai_client(config.PLAN_EDIT_AI_PROVIDER or config.CHAT_AI_PROVIDER or config.AI_PROVIDER)


def get_plan_edit_ai_client_dep() -> AIClient:
    """FastAPI dependency for the Plan chat's edit step."""
    return get_plan_edit_ai_client()


def get_ai_client_dep() -> AIClient:
    """FastAPI dependency wrapper around get_ai_client().

    Exposed separately so tests can override the AI client via
    ``app.dependency_overrides`` without mocking the database.
    """
    return get_ai_client()


def get_chat_ai_client_dep() -> AIClient:
    """FastAPI dependency for the fitness chat endpoint."""
    return get_chat_ai_client()
