import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from app.ai.factory import get_ai_client_dep
from app.main import app
from tests.conftest import FakeFitnessChatAIClient


@pytest_asyncio.fixture
async def chat_client():
    fake = FakeFitnessChatAIClient(classify=False)
    app.dependency_overrides[get_ai_client_dep] = lambda: fake
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def classifying_client():
    fake = FakeFitnessChatAIClient(classify=True)
    app.dependency_overrides[get_ai_client_dep] = lambda: fake
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def invalid_level_client():
    fake = FakeFitnessChatAIClient(classify=True, fitness_level="elite")
    app.dependency_overrides[get_ai_client_dep] = lambda: fake
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_first_call_returns_opening_question(chat_client):
    res = await chat_client.post("/fitness-chat", json={"history": [], "message": ""})
    assert res.status_code == 200
    data = res.json()
    assert data["done"] is False
    assert len(data["message"]) > 0
    assert data.get("fitnessLevel") is None


@pytest.mark.asyncio
async def test_mid_conversation_returns_follow_up(chat_client):
    history = [
        {"role": "assistant", "content": "What's your most recent race time?"},
        {"role": "user", "content": "I ran a 10K in 52 minutes last month"},
    ]
    res = await chat_client.post("/fitness-chat", json={"history": history, "message": "About 40 km per week"})
    assert res.status_code == 200
    data = res.json()
    assert data["done"] is False
    assert len(data["message"]) > 0


@pytest.mark.asyncio
async def test_final_turn_returns_classification(classifying_client):
    history = [
        {"role": "assistant", "content": "What's your most recent race time?"},
        {"role": "user", "content": "52-min 10K"},
        {"role": "assistant", "content": "Great! How many km per week?"},
        {"role": "user", "content": "40 km"},
    ]
    res = await classifying_client.post("/fitness-chat", json={"history": history, "message": "18 km longest run"})
    assert res.status_code == 200
    data = res.json()
    assert data["done"] is True
    assert data["fitnessLevel"] in {"beginner", "intermediate", "advanced"}
    assert isinstance(data["vdot"], int)
    assert data["vdot"] == 43
    assert len(data["message"]) > 0
    assert data["weeklyKm"] == 40.0
    assert data["longestRunKm"] == 18.0


@pytest.mark.asyncio
async def test_invalid_fitness_level_returns_422(invalid_level_client):
    res = await invalid_level_client.post("/fitness-chat", json={"history": [], "message": "test"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_long_history_processes_without_error(chat_client):
    history = []
    for i in range(5):
        history.append({"role": "assistant", "content": f"Question {i + 1}?"})
        history.append({"role": "user", "content": f"Answer {i + 1}"})
    res = await chat_client.post("/fitness-chat", json={"history": history, "message": "one more answer"})
    assert res.status_code == 200
    assert res.json()["done"] is False
