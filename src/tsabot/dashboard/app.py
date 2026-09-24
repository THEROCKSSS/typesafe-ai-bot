"""Dashboard server: a local read-only control panel over the bot's SQLite state.

Run:  python -m tsabot.dashboard.app   (or `python src/dashboard_main.py`)
Default: http://127.0.0.1:8788
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
from datetime import timedelta

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import load_config
from ..db import Database, iso, utcnow
from ..policy import RulebookError, load_rules

ROOT = pathlib.Path(__file__).resolve().parents[3]
WEB = pathlib.Path(__file__).resolve().parent / "web"


def create_app(base: pathlib.Path | None = None) -> FastAPI:
    base = base or ROOT
    cfg = load_config(base=base)
    db = Database(cfg.effective_db_path(base))

    app = FastAPI(title="TypeSafe AI Bot — Dashboard", docs_url="/api/docs",
                  openapi_url="/api/openapi.json")
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")
    # Vite (React build) emits /assets/*; serve it when present.
    assets_dir = WEB / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    def q(sql: str, params=()) -> list[dict]:
        try:
            with sqlite3.connect(db.path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError:
            return []  # DB not initialized yet — render empty states

    # ---- pages ------------------------------------------------------
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB / "index.html")

    @app.get("/briefing")
    def briefing() -> FileResponse:
        """Team briefing page — standalone, screenshot-friendly, 3D hero."""
        return FileResponse(base / "docs" / "briefing.html")

    @app.get("/cases")
    @app.get("/cases/{case_id}")
    @app.get("/votes")
    @app.get("/votes/{vote_id}")
    @app.get("/judge")
    @app.get("/rulebook")
    @app.get("/rules")
    @app.get("/loadtest")
    @app.get("/scheduler")
    @app.get("/events")
    @app.get("/guide")
    @app.get("/case/{case_id}")
    @app.get("/vote/{vote_id}")
    def spa(case_id: int | None = None, vote_id: int | None = None) -> FileResponse:
        return FileResponse(WEB / "index.html")  # client-side routed, refresh-safe

    # ---- api --------------------------------------------------------
    @app.get("/api/summary")
    def summary() -> JSONResponse:
        cases_7d = q("SELECT COUNT(*) AS n FROM cases WHERE created_at>=?",
                     (iso(utcnow() - timedelta(days=7)),))
        by_action = q("SELECT action, COUNT(*) AS n FROM cases "
                      "WHERE created_at>=? GROUP BY action ORDER BY n DESC",
                      (iso(utcnow() - timedelta(days=7)),))
        open_votes = q("SELECT COUNT(*) AS n FROM votes WHERE status='open'")
        pending_jobs = q("SELECT COUNT(*) AS n FROM scheduled_jobs WHERE status='pending'")
        dry_cases = q("SELECT COUNT(*) AS n FROM cases WHERE dry_run=1")
        judge = q("SELECT COUNT(*) AS n, COALESCE(SUM(input_tokens),0) AS tok, "
                  "COALESCE(AVG(latency_ms),0) AS lat, "
                  "COALESCE(SUM(ok),0) AS ok FROM judge_calls WHERE created_at>=?",
                  (iso(utcnow() - timedelta(hours=24)),))
        jd = judge[0] if judge else {"n": 0, "tok": 0, "lat": 0, "ok": 0}
        return JSONResponse({
            "config": {
                "dry_run": cfg.dry_run,
                # string: JS numbers lose precision on 64-bit snowflakes
                "guild_id": str(cfg.guild_id or ""),
                "spam_timeout_minutes": cfg.spam_timeout_minutes,
                "vote_min": cfg.vote_min,
                "vote_pct": cfg.vote_pct,
                "vote_minutes": cfg.vote_minutes,
                "jev_model": cfg.jev_model,
            },
            "cases_7d": cases_7d[0]["n"] if cases_7d else 0,
            "cases_by_action": by_action,
            "open_votes": open_votes[0]["n"] if open_votes else 0,
            "pending_jobs": pending_jobs[0]["n"] if pending_jobs else 0,
            "dry_run_cases": dry_cases[0]["n"] if dry_cases else 0,
            "judge_24h": {
                "calls": jd["n"], "ok": jd["ok"], "tokens": jd["tok"],
                "avg_latency_ms": int(jd["lat"] or 0),
                "est_cost_usd": round((jd["tok"] or 0) * 0.042 / 1_000_000, 6),
            },
            "generated_at": iso(utcnow()),
        })

    @app.get("/api/judge")
    def judge_api() -> JSONResponse:
        since = iso(utcnow() - timedelta(hours=24))
        by_layer = q("SELECT layer, COUNT(*) AS n FROM judge_calls WHERE created_at>=? "
                     "GROUP BY layer ORDER BY n DESC", (since,))
        series = q("SELECT created_at, latency_ms, input_tokens, layer, ok "
                   "FROM judge_calls WHERE created_at>=? ORDER BY id DESC LIMIT 120",
                   (since,))
        recent = q("SELECT created_at, layer, model, ok, input_tokens, latency_ms, error "
                   "FROM judge_calls ORDER BY id DESC LIMIT 30")
        last_error = q("SELECT error FROM judge_calls WHERE ok=0 AND error IS NOT NULL "
                       "ORDER BY id DESC LIMIT 1")
        return JSONResponse({
            "by_layer": by_layer,
            "series": list(reversed(series)),
            "recent": recent,
            "last_error": last_error[0]["error"] if last_error else None,
        })

    @app.get("/api/cases")
    def cases_api(limit: int = 50, offset: int = 0, action: str | None = None,
                  target_id: int | None = None) -> JSONResponse:
        limit = max(1, min(limit, 200))
        where, params = [], []
        if action:
            where.append("action=?")
            params.append(action)
        if target_id:
            where.append("target_id=?")
            params.append(target_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params += [limit, offset]
        rows = q(f"SELECT * FROM cases {clause} ORDER BY id DESC LIMIT ? OFFSET ?", params)
        total = q(f"SELECT COUNT(*) AS n FROM cases {clause}", params[:-2])
        return JSONResponse({"total": total[0]["n"] if total else 0,
                             "rows": rows})

    @app.get("/api/case/{case_id}")
    def case_api(case_id: int) -> JSONResponse:
        rows = q("SELECT * FROM cases WHERE id=?", (case_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="case not found")
        return JSONResponse(rows[0])

    @app.get("/api/votes")
    def votes_api() -> JSONResponse:
        votes = q("SELECT v.*, "
                  "(SELECT COUNT(*) FROM vote_ballots b WHERE b.vote_id=v.id) AS total_ballots "
                  "FROM votes v ORDER BY v.id DESC LIMIT 100")
        for v in votes:
            counts = q("SELECT choice, COUNT(*) AS n FROM vote_ballots WHERE vote_id=? "
                       "GROUP BY choice", (v["id"],))
            v["counts"] = {c["choice"]: c["n"] for c in counts}
        return JSONResponse({"votes": votes})
    @app.get("/api/vote/{vote_id}")
    def vote_api(vote_id: int) -> JSONResponse:
        rows = q("SELECT * FROM votes WHERE id=?", (vote_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="vote not found")
        v = rows[0]
        ballots = q("SELECT user_id, choice, created_at FROM vote_ballots "
                    "WHERE vote_id=? ORDER BY id", (vote_id,))
        counts = q("SELECT choice, COUNT(*) AS n FROM vote_ballots WHERE vote_id=? "
                   "GROUP BY choice", (vote_id,))
        v["ballots"] = ballots
        v["counts"] = {c["choice"]: c["n"] for c in counts}
        return JSONResponse(v)

    @app.get("/api/rules")
    def rules_api() -> JSONResponse:
        try:
            rules = load_rules(cfg.effective_rules_path(base))
            return JSONResponse({"rules": rules, "path": str(cfg.effective_rules_path(base))})
        except RulebookError as e:
            return JSONResponse({"rules": [], "error": str(e),
                                 "path": str(cfg.effective_rules_path(base))})

    @app.get("/api/events")
    def events_api() -> JSONResponse:
        jobs = q("SELECT id, kind, payload_json, due_at, status, error, created_at "
                 "FROM scheduled_jobs ORDER BY id DESC LIMIT 40")
        owners = q("SELECT * FROM owners ORDER BY kind, subject_id")
        caps = q("SELECT role_id, capability FROM role_caps ORDER BY role_id")
        return JSONResponse({"jobs": jobs, "owners": owners, "caps": caps})

    @app.get("/api/loadtest")
    def loadtest_api() -> JSONResponse:
        """Read whichever load-test result file exists (live preferred, then local)."""
        for name in ("loadtest_live.json", "loadtest_results.json"):
            p = base / "data" / name
            if p.is_file():
                try:
                    summary = json.loads(p.read_text(encoding="utf-8"))
                    summary["file"] = name
                    return JSONResponse({"available": True, "summary": summary})
                except Exception as e:  # noqa: BLE001
                    return JSONResponse({"available": False, "error": str(e)})
        return JSONResponse({"available": False})

    # ---- Discord actions (token stays server-side) -------------------
    DISCORD_API = "https://discord.com/api/v10"
    UA = "DiscordBot (https://local, 0.1) tsabot-dashboard"

    def _discord(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            DISCORD_API + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method)
        req.add_header("Authorization", "Bot " + cfg.discord_token)
        req.add_header("User-Agent", UA)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw.strip() else {})
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode() or "{}")
            except Exception:
                return e.code, {"error": f"HTTP {e.code}"}
        except Exception as e:  # noqa: BLE001
            return 0, {"error": str(e)}

    @app.get("/api/discord/channels")
    def discord_channels() -> JSONResponse:
        """Guild text channels the bot can see (for the guide poster)."""
        if not cfg.discord_token or not cfg.guild_id:
            return JSONResponse({"channels": [], "error": "Discord not configured"})
        st, chans = _discord("GET", f"/guilds/{cfg.guild_id}/channels")
        if st != 200 or not isinstance(chans, list):
            return JSONResponse({"channels": [], "error": f"HTTP {st}"})
        out = [{"id": c["id"], "name": c["name"], "type": c.get("type")}
               for c in chans if c.get("type") in (0, 5)]  # text + announcement
        out.sort(key=lambda c: c["name"])
        return JSONResponse({"channels": out})

    @app.get("/api/discord/members")
    def discord_members() -> JSONResponse:
        if not cfg.discord_token or not cfg.guild_id:
            return JSONResponse({"members": [], "error": "Discord not configured"})
        st, mem = _discord("GET", f"/guilds/{cfg.guild_id}/members?limit=100")
        if st != 200 or not isinstance(mem, list):
            return JSONResponse({"members": [], "error": f"HTTP {st}"})
        out = []
        for m in mem:
            u = m.get("user", {})
            if u.get("bot"):
                continue
            name = m.get("nick") or u.get("global_name") or u.get("username")
            out.append({"id": u.get("id"), "name": name})
        out.sort(key=lambda m: (m["name"] or "").lower())
        return JSONResponse({"members": out})

    @app.post("/api/discord/post")
    async def discord_post(payload: dict = Body(...)) -> JSONResponse:
        """Post a guide message to a channel AS the bot."""
        channel_id = payload.get("channel_id")
        content = (payload.get("content") or "").strip()
        if not channel_id or not content:
            return JSONResponse({"ok": False, "error": "channel_id and content required"},
                                status_code=400)
        if len(content) > 1900:
            return JSONResponse({"ok": False, "error": "content too long (1900 max)"},
                                status_code=400)
        st, res = _discord("POST", f"/channels/{channel_id}/messages",
                           {"content": content, "allowed_mentions": {"parse": []}})
        if st in (200, 201):
            return JSONResponse({"ok": True, "channel": res.get("id") and channel_id,
                                 "message_id": res.get("id")})
        return JSONResponse({"ok": False, "error": res.get("message") or f"HTTP {st}"})

    @app.post("/api/discord/dm")
    async def discord_dm(payload: dict = Body(...)) -> JSONResponse:
        """DM a guide message to a member AS the bot."""
        user_id = payload.get("user_id")
        content = (payload.get("content") or "").strip()
        if not user_id or not content:
            return JSONResponse({"ok": False, "error": "user_id and content required"},
                                status_code=400)
        if len(content) > 1900:
            return JSONResponse({"ok": False, "error": "content too long (1900 max)"},
                                status_code=400)
        st, ch = _discord("POST", "/users/@me/channels", {"recipient_id": str(user_id)})
        if st not in (200, 201):
            return JSONResponse({"ok": False,
                                 "error": ch.get("message") or f"HTTP {st} (closed DMs?)"})
        dm_id = ch.get("id")
        st2, res = _discord("POST", f"/channels/{dm_id}/messages",
                            {"content": content, "allowed_mentions": {"parse": []}})
        if st2 in (200, 201):
            return JSONResponse({"ok": True, "user": user_id, "message_id": res.get("id")})
        return JSONResponse({"ok": False, "error": res.get("message") or f"HTTP {st2}"})

    @app.get("/api/health")
    def health() -> JSONResponse:
        db_ok = True
        try:
            q("SELECT 1")
        except Exception:
            db_ok = False
        return JSONResponse({"status": "ok" if db_ok else "degraded",
                             "db": str(db.path), "dry_run": cfg.dry_run})

    return app


def run() -> None:
    import uvicorn
    cfg = load_config(base=ROOT)
    uvicorn.run(create_app(ROOT), host="127.0.0.1", port=cfg.dashboard_port,
                log_level="info")


app = create_app()

if __name__ == "__main__":
    run()
