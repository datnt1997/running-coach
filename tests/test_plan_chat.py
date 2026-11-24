"""Plan chat: one persistent conversation per Runner, through the HTTP API."""
import asyncio

import pytest_asyncio

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
    assert 19 <= len(history) <= 30 and history[0]["role"] == "user" and history[-1] == {"role": "user", "content": "câu hỏi cuối"}
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

    assert max(sizes[i] for i in range(40, 81)) <= max(sizes[i] for i in range(20, 40)) * 1.5
    assert len([m for m in chat_ai.chat_calls[-1] if m["role"] != "system"]) <= 31


async def test_a_failed_summary_does_not_fail_the_turn_and_is_retried(client, chat_ai):
    chat_ai.fail_summary = True
    for i in range(35):
        assert (await _say(client, f"tin nhắn số {i:03d}")).status_code == 200
    assert len([m for m in chat_ai.chat_calls[-1] if m["role"] != "system"]) <= 31

    chat_ai.fail_summary = False
    await _say(client, "một tin nữa")
    assert "SUMMARY" in _prompt_text(chat_ai.chat_calls[-1], "system")
