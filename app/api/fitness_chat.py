import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ai.client import AIClient
from app.ai.factory import get_chat_ai_client_dep
from app.i18n import (
    chat_missing,
    chat_opener,
    chat_reasoning,
    chat_starter,
    language_instruction,
)
from app.vdot import planner_label, race_time_for_vdot, vdot_from_race

logger = logging.getLogger(__name__)
router = APIRouter()

_SYSTEM_PROMPT = """You are a warm, encouraging running coach helping a runner discover their fitness level before we build their training plan. You only collect information; the app computes VDOT and predictions itself, so never calculate or state a VDOT.

The conversation already began with a question about the race distance (5K, 10K, half marathon, or full marathon). Collect these signals:

1. The race distance of a recent race. The runner is answering the opening question; if they have no recent race, accept the distance they would pick to estimate their current ability. Ask again, briefly, only if the answer is not one of the four distances.
2. Their finish time for that distance. Name the distance in the question (for example "Bạn chạy bán marathon hết bao lâu?"). Never ask for a time without naming the distance. If they have no recent race, ask what time they believe they could run for that distance today, and use that.
3. Their typical weekly running distance in kilometres.
4. The longest single run they've done in the last 3 months.

Always reply to the runner in Vietnamese (tiếng Việt), warm and natural. Keep the JSON block's keys and values in English exactly as specified below.

Ask naturally, one question at a time. If they've already answered one, skip it and acknowledge what they said. Keep it brief and warm; this is a conversation, not a form.

Once you have all the signals, write a short encouraging summary (no VDOT), then end your message with a JSON block in exactly this format:

```json
{
  "race_distance": "10k",
  "race_time": "52:00",
  "weekly_km": 40,
  "longest_run_km": 18
}
```

Rules for the JSON block:
- race_distance must be exactly one of: 5k, 10k, half_marathon, full_marathon
- race_time is "MM:SS" or "H:MM:SS"
- Do not include the JSON block until you have all the signals"""

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

_RACE_METERS = {
    "5k": 5000,
    "10k": 10000,
    "half_marathon": 21097.5,
    "full_marathon": 42195,
}
_RACE_LABELS = {"5k": "5K", "10k": "10K", "half_marathon": "HM", "full_marathon": "FM"}


class ChatMessage(BaseModel):
    role: str
    content: str


class FitnessChatRequest(BaseModel):
    history: list[ChatMessage]
    message: str


class FitnessChatResponse(BaseModel):
    done: bool
    message: str
    fitnessLevel: Optional[str] = None
    vdot: Optional[float] = None
    predictions: Optional[dict[str, str]] = None
    weeklyKm: Optional[float] = None
    longestRunKm: Optional[float] = None
    reasoning: Optional[str] = None


def _parse_time(text: object) -> int | None:
    """'MM:SS' or 'H:MM:SS' -> seconds, or None."""
    parts = str(text).strip().split(":")
    if len(parts) not in (2, 3) or not all(p.strip().isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    seconds = nums[0] * 60 + nums[1] if len(nums) == 2 else nums[0] * 3600 + nums[1] * 60 + nums[2]
    return seconds if seconds > 0 else None


def format_time(seconds: float) -> str:
    total = round(seconds)
    h, rest = divmod(total, 3600)
    m, sec = divmod(rest, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return float(value)


def assess(data: dict) -> tuple[dict | None, list[str]]:
    """Validate the model's signals and compute the result in code.

    Returns (result, []) when every signal is usable, else (None, missing_keys).
    """
    missing: list[str] = []

    distance = data.get("race_distance")
    seconds = _parse_time(data.get("race_time"))
    vdot = None
    if distance in _RACE_METERS and seconds:
        raw = vdot_from_race(_RACE_METERS[distance], seconds)
        if 15 <= raw <= 90:
            vdot = raw
    if vdot is None:
        missing.append("race")

    weekly_km = _number(data.get("weekly_km"))
    if weekly_km is None:
        missing.append("weekly_km")
    longest_run_km = _number(data.get("longest_run_km"))
    if longest_run_km is None:
        missing.append("longest_run_km")

    if missing:
        return None, missing

    # Predictions use the unrounded VDOT so the runner's own race round-trips;
    # only the displayed value is rounded.
    return {
        "fitness_level": planner_label(vdot),
        "vdot": round(vdot, 1),
        "predictions": {
            key: format_time(race_time_for_vdot(vdot, meters)) for key, meters in _RACE_METERS.items()
        },
        "weekly_km": weekly_km,
        "longest_run_km": longest_run_km,
        "reasoning": chat_reasoning(round(vdot, 1), _RACE_LABELS[distance], format_time(seconds)),
    }, []


@router.post("/fitness-chat", response_model=FitnessChatResponse)
async def fitness_chat(
    req: FitnessChatRequest,
    ai_client: AIClient = Depends(get_chat_ai_client_dep),
) -> FitnessChatResponse:
    user_text = req.message.strip()

    # First turn: the distance is asked by code, so the model never asks a time without one.
    if not req.history and not user_text:
        return FitnessChatResponse(done=False, message=chat_opener())

    messages: list[dict] = [
        {"role": "system", "content": f"{_SYSTEM_PROMPT}\n\n{language_instruction()}"}
    ]
    if not req.history:
        messages.append({"role": "assistant", "content": chat_opener()})

    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})

    # Anthropic requires at least one user message in the conversation
    messages.append({"role": "user", "content": user_text or chat_starter()})

    response = await ai_client.generate(messages)
    content = response.content

    match = _JSON_BLOCK_RE.search(content)
    if not match:
        return FitnessChatResponse(done=False, message=content)

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse fitness signals JSON: %s", exc)
        return FitnessChatResponse(done=False, message=_JSON_BLOCK_RE.sub("", content).strip() or content)
    if not isinstance(data, dict):
        data = {}

    result, missing = assess(data)
    if result is None:
        logger.info("Fitness chat ended with missing signals: %s", missing)
        return FitnessChatResponse(done=False, message=chat_missing(missing))

    display_message = _JSON_BLOCK_RE.sub("", content).strip()
    return FitnessChatResponse(
        done=True,
        message=display_message or result["reasoning"],
        fitnessLevel=result["fitness_level"],
        vdot=result["vdot"],
        predictions=result["predictions"],
        weeklyKm=result["weekly_km"],
        longestRunKm=result["longest_run_km"],
        reasoning=result["reasoning"],
    )
