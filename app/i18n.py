from app import config

# Registered languages: code -> name used inside AI prompts.
# To add a language, register it here and add frontend/src/i18n/<code>.js.
LANGUAGES = {"vi": "Vietnamese (tiếng Việt)"}

DEFAULT_LANGUAGE = "vi"

# Opening user message sent when the runner has not typed anything yet.
CHAT_STARTER = {"vi": "Xin chào! Mình muốn được giúp xác định trình độ thể lực của mình."}


def get_language() -> str:
    """Return the configured app language code, raising if it is not registered."""
    code = config.APP_LANGUAGE
    if code not in LANGUAGES:
        raise ValueError(
            f"Unsupported APP_LANGUAGE '{code}'. Registered: {', '.join(sorted(LANGUAGES))}"
        )
    return code


def language_instruction(language: str | None = None) -> str:
    """Prompt line telling the model which language to write user-facing text in."""
    name = LANGUAGES[language or get_language()]
    return (
        f"Write all user-facing text in {name}. Keep enum values, JSON keys and "
        "tool-schema identifiers in English exactly as specified."
    )


def chat_starter(language: str | None = None) -> str:
    return CHAT_STARTER[language or get_language()]
