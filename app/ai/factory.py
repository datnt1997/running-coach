from app import config
from app.ai.client import AIClient


def get_ai_client(provider: str | None = None) -> AIClient:
    provider = provider or config.AI_PROVIDER
    if provider == "anthropic":
        from app.ai.anthropic_client import AnthropicClient

        return AnthropicClient()
    elif provider == "gemini":
        from app.ai.gemini_client import GeminiClient

        return GeminiClient()
    raise ValueError(f"Unknown AI provider: {provider}")


def get_chat_ai_client() -> AIClient:
    """Client for the fitness chat; CHAT_AI_PROVIDER falls back to AI_PROVIDER."""
    return get_ai_client(config.CHAT_AI_PROVIDER or config.AI_PROVIDER)


def get_ai_client_dep() -> AIClient:
    """FastAPI dependency wrapper around get_ai_client().

    Exposed separately so tests can override the AI client via
    ``app.dependency_overrides`` without mocking the database.
    """
    return get_ai_client()


def get_chat_ai_client_dep() -> AIClient:
    """FastAPI dependency for the fitness chat endpoint."""
    return get_chat_ai_client()
