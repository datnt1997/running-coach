from app import config

# Registered languages: code -> name used inside AI prompts.
# To add a language, register it here and add frontend/src/i18n/<code>.js.
LANGUAGES = {"vi": "Vietnamese (tiếng Việt)"}

DEFAULT_LANGUAGE = "vi"

# Opening user message sent when the runner has not typed anything yet.
CHAT_STARTER = {"vi": "Xin chào! Mình muốn được giúp xác định trình độ thể lực của mình."}

# Fixed first turn: the race distance has to be known before the time can be asked,
# so the code asks it instead of leaving the order to the model.
CHAT_OPENER = {
    "vi": (
        "Chào bạn! Để đánh giá thể lực, mình cần một thành tích thi đấu gần đây. "
        "Bạn đã thi đấu cự ly nào: 5K, 10K, bán marathon hay marathon? "
        "(Nếu chưa thi đấu, hãy chọn cự ly bạn muốn ước lượng.)"
    )
}

# Shown when the model ends the chat but a signal is missing or unusable.
CHAT_MISSING = {
    "vi": {
        "prefix": "Mình còn thiếu thông tin: ",
        "suffix": ". Bạn bổ sung giúp mình nhé?",
        "race": "một thành tích thi đấu (cự ly và thời gian) hoặc thời gian ước tính",
        "weekly_km": "số km chạy mỗi tuần",
        "longest_run_km": "quãng đường chạy dài nhất gần đây",
    }
}

# Reasoning line shown with the result.
CHAT_REASONING = {
    "vi": "VDOT {vdot} từ {distance} {time}"
}


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


def chat_opener(language: str | None = None) -> str:
    return CHAT_OPENER[language or get_language()]


def chat_missing(keys: list[str], language: str | None = None) -> str:
    texts = CHAT_MISSING[language or get_language()]
    return texts["prefix"] + ", ".join(texts[k] for k in keys) + texts["suffix"]


def chat_reasoning(vdot: float, distance: str, time: str, language: str | None = None) -> str:
    return CHAT_REASONING[language or get_language()].format(
        vdot=f"{vdot:.1f}", distance=distance, time=time
    )
