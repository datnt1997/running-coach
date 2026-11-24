"""Plan chat: one persistent conversation per Runner, through the HTTP API."""
import asyncio

import pytest_asyncio

from app.agent.plan_chat import MAX_FOLD_BATCH, MAX_VERBATIM
from app.ai.factory import get_chat_ai_client_dep
from app.main import app
from tests.conftest import FakePlanChatAIClient


@pytest_asyncio.fixture
async def chat_ai(client):
    fake = FakePlanChatAIClient()
    app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
    return fake


def _prompt_text(messages, role=None):
    return "\n".join(m["content"] for m in messages if role is None or m["role"] == role)


async def _say(client, text):
    return await client.post("/plan-chat/messages", json={"message": text})


async def test_a_new_runner_has_an_empty_conversation(client, chat_ai):
    resp = await client.get("/plan-chat/messages")
    assert resp.status_code == 200
    assert resp.json() == {"messages": []}


async def test_messages_persist_and_reload_in_order(client, chat_ai):
    resp = await _say(client, "Chào coach")
    assert resp.status_code == 200
    assert [m["role"] for m in resp.json()["messages"]] == ["user", "assistant"]
    await _say(client, "Hôm nay chạy gì?")

    reloaded = (await client.get("/plan-chat/messages")).json()["messages"]
    assert [(m["role"], m["content"]) for m in reloaded] == [
        ("user", "Chào coach"), ("assistant", "reply 1"),
        ("user", "Hôm nay chạy gì?"), ("assistant", "reply 2"),
    ]


async def test_a_blank_message_is_rejected(client, chat_ai):
    assert (await _say(client, "   ")).status_code == 422
    assert chat_ai.calls == []


async def test_each_turn_prompt_has_profile_plan_and_the_last_20_messages(client, chat_ai, seeded_plan):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})
    for i in range(17):  # 34 stored messages after the loop, enough to fold the older ones
        await _say(client, f"tin nhắn số {i}")
    await _say(client, "câu hỏi cuối")

    prompt = chat_ai.calls[-1]
    system = _prompt_text(prompt, "system")
    assert "190" in system and "50" in system          # profile
    assert "Z2" in system and "Test plan" in system     # zones and the Plan
    assert "easy" in system and "8.0" in system         # a Planned workout

    history = [m for m in prompt if m["role"] != "system"]
    assert 19 <= len(history) <= MAX_VERBATIM and history[0]["role"] == "user" and history[-1] == {"role": "user", "content": "câu hỏi cuối"}
    assert "tin nhắn số 16" in _prompt_text(history)
    assert "tin nhắn số 0" not in _prompt_text(history)
    # Raw messages stay stored even when they leave the prompt.
    assert len((await client.get("/plan-chat/messages")).json()["messages"]) == 36


async def test_profile_is_reread_every_turn(client, chat_ai):
    await _say(client, "một")
    assert "chưa nhập" in _prompt_text(chat_ai.calls[-1], "system").lower()
    await client.put("/profile", json={"maxHr": 188, "restingHr": 48})
    await _say(client, "hai")
    assert "188" in _prompt_text(chat_ai.calls[-1], "system")


async def test_prompt_carries_the_gem_tone_and_the_pain_and_medical_rule(client, chat_ai):
    await _say(client, "đau gối")
    system = _prompt_text(chat_ai.calls[-1], "system").lower()
    assert "vietnamese" in system
    assert "table" in system and "zone" in system
    for phrase in ("never diagnose", "see a doctor", "sharp pain", "chest", "dizziness"):
        assert phrase in system, phrase


async def test_personal_numbers_come_from_the_profile_not_the_fixed_prompt(client, chat_ai):
    await _say(client, "một")
    without = _prompt_text(chat_ai.calls[-1], "system")
    await client.put("/profile", json={"maxHr": 197, "restingHr": 41})
    await _say(client, "hai")
    with_profile = _prompt_text(chat_ai.calls[-1], "system")
    assert "197" not in without and "197" in with_profile


async def test_a_failed_ai_call_keeps_the_message_and_can_be_resent(client, chat_ai):
    chat_ai.fail = True
    resp = await _say(client, "Tuần này mệt quá")
    assert resp.status_code == 502

    stored = (await client.get("/plan-chat/messages")).json()["messages"]
    assert [(m["role"], m["content"]) for m in stored] == [("user", "Tuần này mệt quá")]

    chat_ai.fail = False
    retry = await client.post("/plan-chat/retry")
    assert retry.status_code == 200
    stored = (await client.get("/plan-chat/messages")).json()["messages"]
    assert [(m["role"], m["content"]) for m in stored] == [
        ("user", "Tuần này mệt quá"), ("assistant", "reply 2"),
    ]


async def test_retry_with_nothing_to_answer_is_refused(client, chat_ai):
    assert (await client.post("/plan-chat/retry")).status_code == 409
    await _say(client, "xin chào")
    assert (await client.post("/plan-chat/retry")).status_code == 409


async def test_history_sent_to_the_model_never_starts_with_an_assistant_message(client, chat_ai):
    for i in range(11):  # 21 stored messages: the last 20 would start with a reply
        await _say(client, f"tin {i}")
    history = [m for m in chat_ai.calls[-1] if m["role"] != "system"]
    assert history[0]["role"] == "user"
    assert history[-1] == {"role": "user", "content": "tin 10"}


async def test_plan_block_gives_bpm_ranges_for_each_target_zone(client, chat_ai, seeded_plan):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})
    await _say(client, "xin chào")
    system = _prompt_text(chat_ai.calls[-1], "system")
    plan_part = system[system.index("PLAN (current"):]
    assert "bpm" in plan_part
    assert "Z2" in plan_part and "-" in plan_part.split("Z2", 1)[1].split("\n", 1)[0]


async def test_concurrent_retries_store_a_single_reply(client, chat_ai):
    chat_ai.fail = True
    await _say(client, "mệt quá")
    chat_ai.fail = False
    chat_ai.delay = 0.2
    first, second = await asyncio.gather(client.post("/plan-chat/retry"), client.post("/plan-chat/retry"))
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    stored = (await client.get("/plan-chat/messages")).json()["messages"]
    assert [m["role"] for m in stored] == ["user", "assistant"]
    assert len(chat_ai.calls) == 2  # the failed send and one retry


async def test_the_database_is_not_held_in_a_transaction_during_the_ai_call(client, chat_ai):
    from app.db.connection import get_pool

    seen = []
    original = chat_ai.generate

    async def spy(messages, tools=None, response_format=None):
        async with get_pool().connection() as other:
            cur = await other.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                " AND state = 'idle in transaction'"
            )
            seen.append((await cur.fetchone())[0])
        return await original(messages, tools, response_format)

    chat_ai.generate = spy
    assert (await _say(client, "một")).status_code == 200
    assert seen == [0]


async def test_prompt_states_today_so_the_coach_never_asks_the_date(client, chat_ai):
    from datetime import date

    await _say(client, "Bài tập hôm nay?")
    system = _prompt_text(chat_ai.calls[-1], role="system")
    assert date.today().isoformat() in system
    assert "never ask the runner what day it is" in system


# ---- Rolling summary: older messages are compressed, never dropped ----

async def test_a_fact_from_50_turns_ago_is_still_in_the_prompt(client, chat_ai):
    await _say(client, "Gối trái của tôi từng bị chấn thương dây chằng")
    for i in range(1, 56):
        await _say(client, f"tin nhắn số {i:03d}")

    final = chat_ai.chat_calls[-1]
    assert "dây chằng" in _prompt_text(final)
    # The early message is no longer verbatim: it reached the model through the Rolling summary.
    assert "dây chằng" not in _prompt_text(final, "user")
    assert "dây chằng" in _prompt_text(final, "system")


async def test_raw_messages_stay_stored_after_they_are_summarized(client, chat_ai):
    for i in range(40):
        await _say(client, f"tin nhắn số {i:03d}")

    stored = (await client.get("/plan-chat/messages")).json()["messages"]
    assert len(stored) == 80
    assert stored[0]["content"] == "tin nhắn số 000"
    assert any(chat_ai.is_summary_call(c) for c in chat_ai.calls)


async def test_the_prompt_stays_bounded_as_the_conversation_grows(client, chat_ai):
    sizes = {}
    for i in range(1, 81):
        await _say(client, f"tin nhắn số {i:03d} " + "x" * 200)
        sizes[i] = len(_prompt_text(chat_ai.chat_calls[-1]))

    # 30 verbatim messages of ~220 chars, one summary (<= 4000 chars) and the fixed system prompt
    assert max(sizes.values()) <= 30_000
    assert len([m for m in chat_ai.chat_calls[-1] if m["role"] != "system"]) <= MAX_VERBATIM + 1


async def test_a_failed_summary_does_not_fail_the_turn_and_is_retried(client, chat_ai):
    chat_ai.fail_summary = True
    for i in range(35):
        assert (await _say(client, f"tin nhắn số {i:03d}")).status_code == 200
    assert len([m for m in chat_ai.chat_calls[-1] if m["role"] != "system"]) <= MAX_VERBATIM + 1

    chat_ai.fail_summary = False
    await _say(client, "một tin nữa")
    assert "SUMMARY" in _prompt_text(chat_ai.chat_calls[-1], "system")


async def test_the_summary_call_stays_bounded_after_many_failed_summaries(client, chat_ai):
    chat_ai.fail_summary = True
    for i in range(60):
        await _say(client, f"tin nhắn số {i:03d}")
    chat_ai.fail_summary = False
    await _say(client, "một tin nữa")
    await _say(client, "và một tin nữa")

    summary_calls = [c for c in chat_ai.calls if chat_ai.is_summary_call(c)]
    assert summary_calls
    for call in summary_calls:
        transcript = call[1]["content"].split("OLDER MESSAGES:\n")[1]
        assert len([l for l in transcript.splitlines() if l]) <= MAX_FOLD_BATCH


async def test_a_backlog_after_failed_summaries_is_folded_oldest_first(client, chat_ai):
    await _say(client, "Tôi bị đau gót chân phải từ tháng trước")
    chat_ai.fail_summary = True
    for i in range(40):
        await _say(client, f"tin nhắn số {i:03d}")
    chat_ai.fail_summary = False
    for i in range(5):
        await _say(client, f"tin nhắn sau {i}")

    assert "đau gót chân" in _prompt_text(chat_ai.chat_calls[-1], "system")


# ---- Strava log and taper (#37) ----

async def _log_activity(runner_id, strava_id, day, km, matched_workout_id=None, avg_hr=None,
                        hr_adherence=None, pace_adherence=None, load_adherence=None):
    from app.db.connection import get_pool

    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO activity_analyses (strava_activity_id, matched_workout_id, activity_date, distance_km,"
            " pace_adherence, hr_adherence, load_adherence, runner_id, avg_hr_bpm)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (strava_id, matched_workout_id, day, km, pace_adherence, hr_adherence, load_adherence, runner_id, avg_hr),
        )
        await conn.commit()


async def _set_race_in(days):
    from datetime import date, timedelta
    from app.db.connection import get_pool

    async with get_pool().connection() as conn:
        await conn.execute("UPDATE user_goals SET race_date = %s", (date.today() + timedelta(days=days),))
        await conn.commit()


async def test_prompt_lists_recent_activities_with_match_adherence_and_hr_vs_target_zone(
    client, chat_ai, seeded_plan, runner_id
):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})
    await _log_activity(runner_id, 1, seeded_plan["date"], 8.2, seeded_plan["workout_id"], avg_hr=151,
                        hr_adherence="too high", pace_adherence="on target", load_adherence="on target")
    await _say(client, "Tuần này sao?")
    system = _prompt_text(chat_ai.calls[-1], "system")
    assert "RECENT ACTIVITIES" in system
    assert "8.2 km" in system and "matched to easy 8.0 km" in system
    assert "too high" in system and "on target" in system
    assert "average heart rate 151 bpm" in system and "target Z2" in system and "bpm)" in system


async def test_missing_heart_rate_and_unmatched_activity_are_stated(client, chat_ai, seeded_plan, runner_id):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})
    await _log_activity(runner_id, 2, seeded_plan["date"], 5.0, seeded_plan["workout_id"], avg_hr=None)
    await _log_activity(runner_id, 3, seeded_plan["date"], 3.0, None, avg_hr=140)
    await _say(client, "Hi")
    system = _prompt_text(chat_ai.calls[-1], "system")
    assert "average heart rate unavailable" in system
    assert "unmatched" in system


async def test_activities_of_another_runner_never_reach_the_prompt(client, chat_ai, seeded_plan):
    from tests.conftest import make_runner

    other = await make_runner("stranger@example.com")
    await _log_activity(other, 99, seeded_plan["date"], 41.7, None, avg_hr=111)
    await _say(client, "Hi")
    system = _prompt_text(chat_ai.calls[-1], "system")
    assert "41.7" not in system
    assert "no Activities" in system


async def test_taper_guidance_counts_down_to_the_fixed_race_date_and_uses_the_plan(
    client, chat_ai, seeded_plan
):
    from datetime import date, timedelta

    await _set_race_in(17)
    await _say(client, "Taper thế nào?")
    system = _prompt_text(chat_ai.calls[-1], "system")
    race = (date.today() + timedelta(days=17)).isoformat()
    assert "17 days" in system and race in system
    assert "TAPER" in system and "race date is fixed" in system
    assert "imported Plan" in system
    assert "fatigue or pain" in system


async def test_no_taper_guidance_far_from_the_race(client, chat_ai, seeded_plan):
    await _say(client, "Hi")
    system = _prompt_text(chat_ai.calls[-1], "system")
    assert "112 days" in system
    assert "TAPER" not in system


# ---- review fixes for #37 (pure prompt tests) ----

def _goal(days):
    from datetime import date, timedelta
    return {"race_date": date.today() + timedelta(days=days), "distance": "10k", "target_time": "50:00"}


def _system(goal, plan=None, activities=None):
    from app.agent.plan_chat import build_messages
    return build_messages(None, goal, plan, [{"role": "user", "content": "hi"}], activities=activities)[0]["content"]


def test_past_race_says_it_has_passed_with_no_negative_days_or_taper():
    system = _system(_goal(-3))
    assert "has passed" in system
    assert "-3" not in system and "TAPER" not in system


def test_race_day_today_says_so():
    system = _system(_goal(0))
    assert "race day is today" in system.lower()
    assert "0 days" not in system


def test_race_countdown_appears_without_a_plan():
    system = _system(_goal(10))
    assert "RACE COUNTDOWN" in system and "10 days" in system


def test_matched_workout_without_distance_omits_zero_km():
    from datetime import date
    act = {"activity_date": date.today(), "distance_km": 5.0, "workout_type": "easy", "planned_distance_km": None,
           "mismatch": True, "avg_hr_bpm": None, "pace_adherence": None, "hr_adherence": None,
           "load_adherence": None}
    system = _system(None, activities=[act])
    assert "matched to easy" in system
    assert "0.0 km" not in system and "mismatched" not in system


async def test_live_strava_runs_reach_the_prompt_without_a_stored_analysis(
    client, chat_ai, fake_strava_client, seeded_strava_connection, seeded_plan
):
    from app.api.strava import get_strava_client
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    await _say(client, "Lấy tracklog ngày 20/11")
    system = _prompt_text(chat_ai.calls[-1], "system")
    assert "2026-11-20: 10.0 km" in system and "pace 5:00/km" in system
    assert "average heart rate 150 bpm" in system
    assert "2026-11-18: 5.0 km" in system  # the second run; the ride is left out
    assert "20.0 km" not in system


async def test_a_strava_outage_falls_back_to_stored_analyses(
    client, chat_ai, fake_strava_client, seeded_strava_connection, seeded_plan, runner_id
):
    from app.api.strava import get_strava_client

    async def boom(access_token, limit=10):
        raise RuntimeError("down")
    fake_strava_client.list_activities = boom
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    await _log_activity(runner_id, 9, seeded_plan["date"], 7.7, seeded_plan["workout_id"], avg_hr=140)
    resp = await client.post("/plan-chat/messages", json={"message": "Hi"})
    assert resp.status_code == 200
    assert "7.7 km" in _prompt_text(chat_ai.calls[-1], "system")


async def test_an_unmatched_run_carries_the_plan_workout_and_zone_for_analysis(client, chat_ai, seeded_plan, runner_id):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})
    await _log_activity(runner_id, 4, seeded_plan["date"], 9.0, None, avg_hr=150)
    await _say(client, "Phân tích buổi chạy hôm nay")
    system = _prompt_text(chat_ai.calls[-1], "system")
    assert "unmatched" in system
    assert "Plan that day: easy" in system and "target Z2" in system
    assert "average heart rate falls in Z" in system
    assert "Analyse any run the runner asks about, matched or not" in system
