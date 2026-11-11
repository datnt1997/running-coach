"""Verification-only ASGI entry point: the real app with the AI boundary faked.

Run via launch.sh (cwd = repo root). The only thing replaced is the AIClient,
the production boundary to Anthropic/Gemini, so verification costs nothing and
is deterministic. Routes, DB, migrations, SPA serving are all the real ones.
"""
import json

from app.ai.client import AIResponse, ToolCall, TokenUsage
from app.ai.factory import get_ai_client_dep, get_chat_ai_client_dep
from app.main import app

PHASES = [("base", 4), ("build", 4), ("peak", 2), ("taper", 2)]
SIGNALS = {"sex": "male", "age": 30, "race_distance": "10k", "race_time": "52:00",
           "weekly_km": 40, "longest_run_km": 18}


def _plan_arguments() -> dict:
    weeks, n = [], 0
    for phase, count in PHASES:
        for _ in range(count):
            n += 1
            weeks.append({"week_number": n, "phase": phase, "workouts": [
                {"day": "Mon", "type": "easy", "distance_km": 6.0, "pace_zone": "Z2", "notes": "VERIFY easy"},
                {"day": "Wed", "type": "tempo" if phase != "base" else "easy", "distance_km": 8.0, "pace_zone": "Z3", "notes": "VERIFY quality"},
                {"day": "Sat", "type": "long", "distance_km": 10.0 + n, "pace_zone": "Z2", "notes": "VERIFY long"},
            ]})
    return {"summary": "VERIFY-FAKE-PLAN 12 weeks", "total_weeks": n,
            "phase_breakdown": dict(PHASES), "weeks": weeks}


class VerifyFakeAI:
    async def generate(self, messages, tools=None, response_format=None) -> AIResponse:
        usage = TokenUsage(input_tokens=1, output_tokens=1)
        if tools:  # plan generation
            return AIResponse(content="", usage=usage,
                              tool_calls=[ToolCall(name="generate_training_plan", arguments=_plan_arguments())])
        # Fitness chat: first user turn is the sex/age answer, the second ends the chat.
        user_turns = sum(1 for m in messages if m["role"] == "user")
        if user_turns < 2:
            return AIResponse(content="Thời gian thi đấu gần nhất của bạn là bao nhiêu?", usage=usage)
        return AIResponse(content="Tuyệt vời!\n\n```json\n" + json.dumps(SIGNALS) + "\n```", usage=usage)


app.dependency_overrides[get_ai_client_dep] = VerifyFakeAI
app.dependency_overrides[get_chat_ai_client_dep] = VerifyFakeAI
