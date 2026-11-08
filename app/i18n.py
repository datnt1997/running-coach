from app import config

# Registered languages: code -> name used inside AI prompts.
# To add a language, register it here and add frontend/src/i18n/<code>.js.
LANGUAGES = {"vi": "Vietnamese (tiếng Việt)"}

DEFAULT_LANGUAGE = "vi"

# Opening user message sent when the runner has not typed anything yet.
CHAT_STARTER = {"vi": "Xin chào! Mình muốn được giúp xác định trình độ thể lực của mình."}

# Fixed first turn: sex and age come before every other question (the book grades
# levels by sex and age), so the code asks it instead of leaving it to the model.
CHAT_OPENER = {
    "vi": (
        "Chào bạn! Trước khi đánh giá thể lực, mình cần biết giới tính (nam hay nữ) "
        "và tuổi của bạn, vì bảng cấp độ của Daniels chấm khác nhau theo giới tính "
        "và độ tuổi. Bạn là nam hay nữ, và bao nhiêu tuổi?"
    )
}

# Shown when the model ends the chat but a signal is missing or unusable.
CHAT_MISSING = {
    "vi": {
        "prefix": "Mình còn thiếu thông tin: ",
        "suffix": ". Bạn bổ sung giúp mình nhé?",
        "sex": "giới tính (nam/nữ, hoặc bỏ qua)",
        "age": "tuổi (hoặc bỏ qua)",
        "race": "một thành tích thi đấu (cự ly và thời gian) hoặc thời gian ước tính",
        "weekly_km": "số km chạy mỗi tuần",
        "longest_run_km": "quãng đường chạy dài nhất gần đây",
    }
}

# Reasoning line shown with the result.
CHAT_REASONING = {
    "vi": "VDOT {vdot} từ {distance} {time}; cấp {level}/10 (Bảng 5.6, Daniels)"
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


def chat_reasoning(vdot: float, distance: str, time: str, level: int, language: str | None = None) -> str:
    return CHAT_REASONING[language or get_language()].format(
        vdot=f"{vdot:.1f}", distance=distance, time=time, level=level
    )
