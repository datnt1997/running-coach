"""Profile facts: the coach proposes, the runner confirms, the facts page edits."""
import pytest_asyncio

from app.ai.factory import get_chat_ai_client_dep
from app.main import app
from tests.conftest import FakePlanChatAIClient

PROPOSAL = "Mình sẽ ghi nhớ: đầu gối trái hay đau. Được không?\n[[REMEMBER: đầu gối trái hay đau]]"


@pytest_asyncio.fixture
async def chat_ai(client):
    fake = FakePlanChatAIClient()
    app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
    return fake


def _system(fake):
    return "\n".join(m["content"] for m in fake.calls[-1] if m["role"] == "system")


async def _say(client, text="gối trái mình hay đau"):
    return await client.post("/plan-chat/messages", json={"message": text})


async def _propose(client, chat_ai, text=PROPOSAL):
    chat_ai.scripted.append(text)
    resp = await _say(client)
    assert resp.status_code == 200
    return resp.json()["messages"][1]


async def _facts(client):
    return (await client.get("/profile-facts")).json()["facts"]


async def test_a_proposal_is_shown_but_nothing_is_saved_until_confirmed(client, chat_ai):
    reply = await _propose(client, chat_ai)

    assert reply["content"] == "Mình sẽ ghi nhớ: đầu gối trái hay đau. Được không?"  # marker hidden
    assert reply["proposal"] == {"text": "đầu gối trái hay đau", "status": "pending"}
    assert await _facts(client) == []
    stored = (await client.get("/plan-chat/messages")).json()["messages"]
    assert stored[1]["proposal"]["status"] == "pending"


async def test_confirming_saves_the_fact_once(client, chat_ai):
    reply = await _propose(client, chat_ai)
    url = f"/plan-chat/messages/{reply['id']}/proposal"

    resp = await client.post(f"{url}/confirm")
    assert resp.status_code == 200
    assert resp.json()["message"]["proposal"]["status"] == "saved"
    assert [f["text"] for f in await _facts(client)] == ["đầu gối trái hay đau"]

    assert (await client.post(f"{url}/confirm")).status_code == 409
    assert len(await _facts(client)) == 1


async def test_declining_saves_nothing(client, chat_ai):
    reply = await _propose(client, chat_ai)
    url = f"/plan-chat/messages/{reply['id']}/proposal"
    resp = await client.post(f"{url}/decline")
    assert resp.status_code == 200
    assert resp.json()["message"]["proposal"]["status"] == "declined"
    assert await _facts(client) == []
    assert (await client.post(f"{url}/confirm")).status_code == 409


async def test_a_message_without_a_proposal_cannot_be_confirmed(client, chat_ai):
    resp = await _say(client)
    reply = resp.json()["messages"][1]
    assert reply["proposal"] is None
    assert (await client.post(f"/plan-chat/messages/{reply['id']}/proposal/confirm")).status_code == 409


async def test_facts_can_be_edited_and_deleted(client, chat_ai):
    reply = await _propose(client, chat_ai)
    await client.post(f"/plan-chat/messages/{reply['id']}/proposal/confirm")
    fact = (await _facts(client))[0]

    resp = await client.put(f"/profile-facts/{fact['id']}", json={"text": "  đầu gối phải hay đau  "})
    assert resp.status_code == 200
    assert [f["text"] for f in await _facts(client)] == ["đầu gối phải hay đau"]

    assert (await client.put(f"/profile-facts/{fact['id']}", json={"text": "  "})).status_code == 422
    assert (await client.delete(f"/profile-facts/{fact['id']}")).status_code == 200
    assert await _facts(client) == []
    assert (await client.delete(f"/profile-facts/{fact['id']}")).status_code == 404
    assert (await client.put(f"/profile-facts/{fact['id']}", json={"text": "x"})).status_code == 404


async def test_saved_facts_are_reread_into_every_later_prompt(client, chat_ai):
    reply = await _propose(client, chat_ai)
    assert "đầu gối trái" not in _system(chat_ai)  # not saved yet
    await client.post(f"/plan-chat/messages/{reply['id']}/proposal/confirm")

    await _say(client, "tuần này chạy gì?")
    assert "đầu gối trái hay đau" in _system(chat_ai)

    fact = (await _facts(client))[0]
    await client.put(f"/profile-facts/{fact['id']}", json={"text": "hay bị chuột rút"})
    await _say(client, "còn hôm nay?")
    assert "hay bị chuột rút" in _system(chat_ai) and "đầu gối trái" not in _system(chat_ai)

    await client.delete(f"/profile-facts/{fact['id']}")
    await _say(client, "ok")
    assert "chuột rút" not in _system(chat_ai)


async def test_the_prompt_tells_the_coach_how_to_propose_a_fact(client, chat_ai):
    await _say(client)
    system = _system(chat_ai)
    assert "[[REMEMBER:" in system and "I'll remember" in system
