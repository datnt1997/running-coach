from app.api import ui


async def test_root_sends_a_visitor_to_the_spa_when_it_is_built(anon_client, monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "FRONTEND_DIST", tmp_path)  # exists
    resp = await anon_client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/app"


async def test_root_serves_the_fallback_page_without_a_frontend_build(anon_client, monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "FRONTEND_DIST", tmp_path / "missing")
    resp = await anon_client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert "Running Coach" in resp.text
