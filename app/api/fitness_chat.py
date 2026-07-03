import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.ai.client import AIClient
from app.ai.factory import get_ai_client_dep

logger = logging.getLogger(__name__)
router = APIRouter()

_SYSTEM_PROMPT = """You are a warm, encouraging running coach helping a runner discover their fitness level before we build their training plan. Your job is to collect three pieces of information through friendly conversation:

1. A recent race time and the race distance (5K, 10K, half marathon, or full marathon)
2. Their typical weekly running distance in kilometres
3. The longest single run they've done in the last 3 months

Ask naturally — one question at a time, in whatever order fits the conversation. If they've already answered one, skip it and acknowledge what they said ("Nice, a 52-minute 10K is a solid base!"). Keep it brief and warm — this is a conversation, not a form.

If the runner has no recent race time, ask what pace feels comfortable and conversational to them, and use that to estimate their VDOT.

Once you have all three signals, classify their fitness level using the VDOT system:

VDOT reference (Daniels-Gilbert):
- 5K 35:00 → VDOT 26 | 5K 30:00 → VDOT 31 | 5K 25:00 → VDOT 38 | 5K 22:00 → VDOT 45 | 5K 20:00 → VDOT 50
- 10K 60:00 → VDOT 32 | 10K 52:00 → VDOT 38 | 10K 50:00 → VDOT 40 | 10K 45:00 → VDOT 45 | 10K 40:00 → VDOT 52
- HM 2:00 → VDOT 36 | HM 1:45 → VDOT 43 | HM 1:30 → VDOT 51
- FM 4:30 → VDOT 33 | FM 4:00 → VDOT 38 | FM 3:30 → VDOT 45

Fitness level thresholds:
- VDOT < 35  → beginner
- VDOT 35–50 → intermediate
- VDOT > 50  → advanced

When you have collected all three signals and are ready to classify, write a short encouraging summary, then end your message with a JSON block in exactly this format:

```json
{
  "fitness_level": "intermediate",
  "vdot": 43,
  "weekly_km": 40,
  "longest_run_km": 18,
  "reasoning": "VDOT 43 from 10K 52:00; 40 km/week; longest run 18 km → intermediate"
}
```

Rules for the JSON block:
- fitness_level must be exactly one of: beginner, intermediate, advanced
- vdot must be a whole number between 20 and 80
- Do not include the JSON block until you have all three signals"""

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_VALID_LEVELS = {"beginner", "intermediate", "advanced"}
_FIRST_CALL_STARTER = "Hi! I'd like some help figuring out my fitness level."


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
    vdot: Optional[int] = None
    weeklyKm: Optional[float] = None
    longestRunKm: Optional[float] = None
    reasoning: Optional[str] = None


@router.post("/fitness-chat", response_model=FitnessChatResponse)
async def fitness_chat(
    req: FitnessChatRequest,
    ai_client: AIClient = Depends(get_ai_client_dep),
) -> FitnessChatResponse:
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})

    user_text = req.message.strip()
    # Anthropic requires at least one user message in the conversation
    messages.append({"role": "user", "content": user_text or _FIRST_CALL_STARTER})

    response = await ai_client.generate(messages)
    content = response.content

    match = _JSON_BLOCK_RE.search(content)
    if match:
        try:
            data = json.loads(match.group(1))
            fitness_level = data.get("fitness_level", "")
            if fitness_level not in _VALID_LEVELS:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "invalid_fitness_level",
                        "message": f"'{fitness_level}' is not a valid fitness level",
                    },
                )
            display_message = _JSON_BLOCK_RE.sub("", content).strip()
            return FitnessChatResponse(
                done=True,
                message=display_message or data.get("reasoning", ""),
                fitnessLevel=fitness_level,
                vdot=int(data.get("vdot", 0)),
                weeklyKm=float(data.get("weekly_km", 0)),
                longestRunKm=float(data.get("longest_run_km", 0)),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse fitness classification JSON: %s", exc)

    return FitnessChatResponse(done=False, message=content)
