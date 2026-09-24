"""Dashboard integration tests - real HTTP calls against a live TestClient."""
import pytest
from fastapi.testclient import TestClient

from tsabot.dashboard.app import create_app
from tsabot.db import Database


@pytest.fixture()
def client(tmp_path):
    # seed a database the dashboard will read
    db = Database(tmp_path / "data" / "tsabot.db")
    db.init()
    db.add_case(guild_id=1, kind="moderation", action="warn", target_id=5,
                actor_id=1, reason="test warning")
    db.add_case(guild_id=1, kind="spam", action="timeout", target_id=6,
                reason="burst", dry_run=True)
    db.create_vote(guild_id=1, target_id=6, reporter_id=2, reason="spam in vc",
                   judge={"reason_valid": 0.9},
                   deadline_at=__import__("tsabot.db", fromlist=["utcnow"]).utcnow())
    db.add_job(guild_id=1, kind="voice_unmute", payload={"member_id": 6},
               due_at=__import__("tsabot.db", fromlist=["utcnow"]).utcnow())
    db.record_judge_call(layer="jev", model="jev-1.13.0", ok=True,
                         input_tokens=100, latency_ms=90)
    (tmp_path / "policy").mkdir(exist_ok=True)
    (tmp_path / "policy" / "rules.json").write_text(
        '{"rules":[{"id":"x","title":"X","description":"d","severity":"high",'
        '"enabled":true,"auto_action":"timeout","timeout_minutes":10}]}', encoding="utf-8")
    (tmp_path / ".env").write_text("DRY_RUN=1\nDASHBOARD_PORT=8799\n", encoding="utf-8")
    app = create_app(tmp_path)
    return TestClient(app)


def test_index_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "TypeSafe AI Bot" in r.text


def test_spa_routes_serve_index(client):
    for path in ("/cases", "/votes", "/judge", "/rulebook", "/loadtest",
                 "/scheduler", "/guide", "/case/1", "/vote/1"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "<!DOCTYPE html>" in r.text


def test_static_assets(client):
    # the Vite/React build emits hashed bundles under /assets; the legacy
    # plain build emitted /static/*. Accept whichever exists and prove it serves.
    index = client.get("/").text
    import re
    refs = re.findall(r'(?:src|href)="(/assets/[^"]+|/static/[^"]+)"', index)
    assert refs, "index.html references no built assets"
    for ref in refs:
        r = client.get(ref)
        assert r.status_code == 200, ref
        assert len(r.content) > 200, ref


def test_summary_api(client):
    r = client.get("/api/summary")
    assert r.status_code == 200
    d = r.json()
    assert d["cases_7d"] == 2
    assert d["open_votes"] == 1
    assert d["pending_jobs"] == 1
    assert d["dry_run_cases"] == 1
    assert d["judge_24h"]["calls"] == 1
    assert d["config"]["dry_run"] is True


def test_cases_api_pagination_and_detail(client):
    r = client.get("/api/cases?limit=1&offset=0")
    d = r.json()
    assert d["total"] == 2 and len(d["rows"]) == 1
    first_id = d["rows"][0]["id"]
    r2 = client.get(f"/api/case/{first_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == first_id
    assert client.get("/api/case/9999").status_code == 404


def test_votes_api(client):
    r = client.get("/api/votes")
    d = r.json()
    assert len(d["votes"]) == 1
    assert "counts" in d["votes"][0]
    vid = d["votes"][0]["id"]
    d2 = client.get(f"/api/vote/{vid}").json()
    assert "ballots" in d2 and "counts" in d2


def test_rules_api(client):
    d = client.get("/api/rules").json()
    assert len(d["rules"]) == 1 and d["rules"][0]["id"] == "x"


def test_events_and_health(client):
    d = client.get("/api/events").json()
    assert len(d["jobs"]) == 1
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["dry_run"] is True


def test_judge_api(client):
    d = client.get("/api/judge").json()
    assert d["by_layer"][0]["layer"] == "jev"
    assert len(d["recent"]) == 1
