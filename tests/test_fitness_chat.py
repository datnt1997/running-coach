import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app.ai.factory import get_chat_ai_client_dep
from app.api.fitness_chat import assess, format_time
from app.main import app
from tests.conftest import FakeFitnessChatAIClient


@pytest_asyncio.fixture
async def make_client():
    """Build a client wired to a fake chat AI; returns (client, fake)."""
    opened: list[httpx.AsyncClient] = []

    async def _make(**kwargs):
        fake = FakeFitnessChatAIClient(**kwargs)
        app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
        ac = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        opened.append(ac)
        return ac, fake

    yield _make
    for ac in opened:
        await ac.aclose()
    app.dependency_overrides.clear()


HISTORY = [
    {"role": "assistant", "content": "Bạn là nam hay nữ, và bao nhiêu tuổi?"},
    {"role": "user", "content": "Nam, 30 tuổi"},
]


@pytest.mark.asyncio
async def test_first_turn_asks_sex_and_age_without_calling_the_model(make_client):
    client, fake = await make_client()
    res = await client.post("/fitness-chat", json={"history": [], "message": ""})
    data = res.json()
    assert res.status_code == 200
    assert data["done"] is False
    assert "giới tính" in data["message"] and "tuổi" in data["message"]
    assert fake.calls == []


@pytest.mark.asyncio
async def test_opener_is_in_the_conversation_the_model_sees(make_client):
    client, fake = await make_client()
    await client.post("/fitness-chat", json={"history": [], "message": "Nam, 30 tuổi"})
    roles = [m["role"] for m in fake.calls[0]]
    assert roles == ["system", "assistant", "user"]
    assert "giới tính" in fake.calls[0][1]["content"]


@pytest.mark.asyncio
async def test_mid_conversation_returns_follow_up(make_client):
    client, _ = await make_client()
    res = await client.post("/fitness-chat", json={"history": HISTORY, "message": "10K 52 phút"})
    data = res.json()
    assert res.status_code == 200
    assert data["done"] is False
    assert data.get("fitnessLevel") is None


@pytest.mark.asyncio
async def test_complete_assessment_is_computed_in_code(make_client):
    client, _ = await make_client(classify=True)
    res = await client.post("/fitness-chat", json={"history": HISTORY, "message": "18 km"})
    data = res.json()
    assert data["done"] is True
    assert data["vdot"] == pytest.approx(38.2, abs=0.1)  # 10K 52:00
    assert data["level"] == 1  # male 30: 38.2 is between level 1 (35.0) and level 2 (40.0)
    assert data["fitnessLevel"] == "beginner"
    assert data["levelGroup"] == "novice"
    assert set(data["predictions"]) == {"5k", "10k", "half_marathon", "full_marathon"}
    assert data["predictions"]["10k"] == "52:00"
    assert data["weeklyKm"] == 40.0
    assert data["longestRunKm"] == 18.0
    assert "VDOT 38.2" in data["reasoning"]
    assert "json" not in data["message"]


@pytest.mark.asyncio
async def test_sex_changes_the_level(make_client):
    results = {}
    for sex in ("male", "female"):
        client, _ = await make_client(classify=True, signals={"sex": sex})
        res = await client.post("/fitness-chat", json={"history": HISTORY, "message": "x"})
        results[sex] = res.json()["level"]
    # VDOT 38.2: male level 1 (35.0-40.0), female level 2 (35.8-40.2)
    assert results == {"male": 1, "female": 2}


@pytest.mark.asyncio
async def test_missing_age_key_is_not_done_and_names_the_gap(make_client):
    client, _ = await make_client(classify=True, drop=("age",))
    res = await client.post("/fitness-chat", json={"history": HISTORY, "message": "x"})
    data = res.json()
    assert data["done"] is False
    assert "tuổi" in data["message"]
    assert data["fitnessLevel"] is None


@pytest.mark.asyncio
async def test_declined_sex_and_age_still_complete(make_client):
    client, _ = await make_client(classify=True, signals={"sex": "unspecified", "age": None})
    res = await client.post("/fitness-chat", json={"history": HISTORY, "message": "x"})
    assert res.json()["done"] is True


@pytest.mark.asyncio
async def test_unusable_race_time_is_not_done(make_client):
    client, _ = await make_client(classify=True, signals={"race_time": "fast"})
    res = await client.post("/fitness-chat", json={"history": HISTORY, "message": "x"})
    data = res.json()
    assert data["done"] is False
    assert "thành tích" in data["message"]


@pytest.mark.asyncio
async def test_long_history_processes_without_error(make_client):
    client, _ = await make_client()
    history = []
    for i in range(5):
        history.append({"role": "assistant", "content": f"Question {i + 1}?"})
        history.append({"role": "user", "content": f"Answer {i + 1}"})
    res = await client.post("/fitness-chat", json={"history": history, "message": "one more answer"})
    assert res.status_code == 200
    assert res.json()["done"] is False


def test_assess_age_adjusts_level():
    base = {"sex": "female", "race_distance": "10k", "race_time": "52:00",
            "weekly_km": 30, "longest_run_km": 15}
    young, _ = assess({**base, "age": 30})
    old, _ = assess({**base, "age": 58})
    assert old["level"] > young["level"]


def test_assess_rejects_bad_signals():
    ok = {"sex": "male", "age": 30, "race_distance": "10k", "race_time": "52:00",
          "weekly_km": 30, "longest_run_km": 15}
    assert assess(ok)[0] is not None
    for key, bad in [("sex", "x"), ("age", 3), ("age", "30"), ("race_distance", "15k"),
                     ("weekly_km", -1), ("longest_run_km", True), ("race_time", "0:00")]:
        result, missing = assess({**ok, key: bad})
        assert result is None and missing, key


def test_format_time():
    assert format_time(52 * 60) == "52:00"
    assert format_time(4 * 3600 + 5) == "4:00:05"
