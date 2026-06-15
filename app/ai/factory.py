from app.ai.client import AIClient
from app.config import AI_PROVIDER


def get_ai_client() -> AIClient:
    if AI_PROVIDER == "anthropic":
        from app.ai.anthropic_client import AnthropicClient

        return AnthropicClient()
    elif AI_PROVIDER == "gemini":
        from app.ai.gemini_client import GeminiClient

        return GeminiClient()
    raise ValueError(f"Unknown AI_PROVIDER: {AI_PROVIDER}")


def get_ai_client_dep() -> AIClient:
    """FastAPI dependency wrapper around get_ai_client().

    Exposed separately so tests can override the AI client via
    ``app.dependency_overrides`` without mocking the database.
    """
    return get_ai_client()
