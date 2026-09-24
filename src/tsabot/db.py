"""SQLite state for TypeSafe AI Bot.

One class, one file. All timestamps are UTC ISO strings.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  action TEXT NOT NULL,
  target_id INTEGER,
  actor_id INTEGER,
  reporter_id INTEGER,
  target_name TEXT,
  actor_name TEXT,
  reporter_name TEXT,
  voice_channel TEXT,
  reason TEXT,
  detail_json TEXT,
  dry_run INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_guild_created ON cases (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_target ON cases (guild_id, target_id, created_at DESC);

CREATE TABLE IF NOT EXISTS votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  channel_id INTEGER,
  message_id INTEGER,
  target_id INTEGER NOT NULL,
  reporter_id INTEGER NOT NULL,
  target_name TEXT,
  reporter_name TEXT,
  reason TEXT NOT NULL,
  judge_json TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  action TEXT,
  ai_verdict TEXT,
  ai_note TEXT,
  deadline_at TEXT,
  created_at TEXT NOT NULL,
  closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_votes_status ON votes (guild_id, status);

CREATE TABLE IF NOT EXISTS vote_ballots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  vote_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  choice TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (vote_id, user_id)
);

CREATE TABLE IF NOT EXISTS role_caps (
  guild_id INTEGER NOT NULL,
  role_id INTEGER NOT NULL,
  capability TEXT NOT NULL,
  PRIMARY KEY (guild_id, role_id, capability)
);

CREATE TABLE IF NOT EXISTS owners (
  guild_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  added_by INTEGER,
  created_at TEXT NOT NULL,
  PRIMARY KEY (guild_id, subject_id, kind)
);

CREATE TABLE IF NOT EXISTS exemptions (
  guild_id INTEGER NOT NULL,
  subject_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  scope TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (guild_id, subject_id, kind, scope)
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  due_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON scheduled_jobs (status, due_at);

CREATE TABLE IF NOT EXISTS config (
  guild_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY (guild_id, key)
);

CREATE TABLE IF NOT EXISTS judge_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  layer TEXT NOT NULL,
  model TEXT,
  ok INTEGER NOT NULL,
  input_tokens INTEGER DEFAULT 0,
  latency_ms INTEGER DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_judge_created ON judge_calls (created_at DESC);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | pathlib.Path):
        self.path = str(path)
        parent = pathlib.Path(self.path).parent
        if str(parent) and str(parent) != ".":
            parent.mkdir(parents=True, exist_ok=True)

    # ---- plumbing ---------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Additive migrations for databases created by earlier versions."""
        migrations = {
            "cases": [("target_name", "TEXT"), ("actor_name", "TEXT"),
                      ("reporter_name", "TEXT"), ("voice_channel", "TEXT")],
            "votes": [("target_name", "TEXT"), ("reporter_name", "TEXT"),
                      ("ai_verdict", "TEXT"), ("ai_note", "TEXT")],
        }
        for table, cols in migrations.items():
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for name, decl in cols:
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._conn() as conn:
            cur = conn.execute(sql, tuple(params))
            return cur.lastrowid or 0

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._conn() as conn:
            cur = conn.execute(sql, tuple(params))
            return cur.fetchone()

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._conn() as conn:
            cur = conn.execute(sql, tuple(params))
            return cur.fetchall()

    # ---- cases ------------------------------------------------------
    def add_case(self, *, guild_id: int, kind: str, action: str, target_id: int | None = None,
                 actor_id: int | None = None, reporter_id: int | None = None,
                 reason: str | None = None, detail: dict | None = None,
                 dry_run: bool = False, target_name: str | None = None,
                 actor_name: str | None = None, reporter_name: str | None = None,
                 voice_channel: str | None = None) -> int:
        return self.execute(
            "INSERT INTO cases (guild_id, kind, action, target_id, actor_id, reporter_id, "
            "target_name, actor_name, reporter_name, voice_channel, "
            "reason, detail_json, dry_run, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (guild_id, kind, action, target_id, actor_id, reporter_id,
             target_name, actor_name, reporter_name, voice_channel,
             reason, json.dumps(detail, default=str) if detail else None,
             1 if dry_run else 0, iso(utcnow())),
        )

    def list_cases(self, *, guild_id: int | None = None, target_id: int | None = None,
                   limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
        where, params = [], []
        if guild_id:
            where.append("guild_id=?")
            params.append(guild_id)
        if target_id:
            where.append("target_id=?")
            params.append(target_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params += [limit, offset]
        return self.query_all(
            f"SELECT * FROM cases {clause} ORDER BY id DESC LIMIT ? OFFSET ?", params)

    def list_recent(self, *, guild_id: int, kind: str | None = None,
                    limit: int = 10) -> list[sqlite3.Row]:
        """Newest cases for a guild, optionally filtered by kind (for /recent)."""
        where = ["guild_id=?"]
        params: list[Any] = [guild_id]
        if kind:
            where.append("kind=?")
            params.append(kind)
        params.append(limit)
        return self.query_all(
            f"SELECT * FROM cases WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?",
            params)

    def count_cases(self, *, guild_id: int | None = None, kind: str | None = None,
                    action: str | None = None, since: datetime | None = None) -> int:
        where, params = [], []
        if guild_id:
            where.append("guild_id=?")
            params.append(guild_id)
        if kind:
            where.append("kind=?")
            params.append(kind)
        if action:
            where.append("action=?")
            params.append(action)
        if since:
            where.append("created_at>=?")
            params.append(iso(since))
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        row = self.query_one(f"SELECT COUNT(*) AS n FROM cases {clause}", params)
        return int(row["n"]) if row else 0

    def invalid_report_count(self, *, guild_id: int, reporter_id: int, days: int = 7) -> int:
        since = iso(utcnow() - timedelta(days=days))
        row = self.query_one(
            "SELECT COUNT(*) AS n FROM cases WHERE guild_id=? AND kind='report' "
            "AND action='invalid' AND reporter_id=? AND created_at>=?",
            (guild_id, reporter_id, since))
        return int(row["n"]) if row else 0

    def reports_since(self, *, guild_id: int, reporter_id: int, hours: int = 24) -> int:
        since = iso(utcnow() - timedelta(hours=hours))
        row = self.query_one(
            "SELECT COUNT(*) AS n FROM votes WHERE guild_id=? AND reporter_id=? AND created_at>=?",
            (guild_id, reporter_id, since))
        return int(row["n"]) if row else 0

    # ---- config kv --------------------------------------------------
    def kv_get(self, guild_id: int, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM config WHERE guild_id=? AND key=?", (guild_id, key))
        return row["value"] if row else default

    def kv_set(self, guild_id: int, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO config (guild_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
            (guild_id, key, value))

    def kv_all(self, guild_id: int) -> dict[str, str]:
        return {r["key"]: r["value"] for r in
                self.query_all("SELECT key, value FROM config WHERE guild_id=?", (guild_id,))}

    # ---- scheduled jobs ---------------------------------------------
    def add_job(self, *, guild_id: int, kind: str, payload: dict, due_at: datetime) -> int:
        return self.execute(
            "INSERT INTO scheduled_jobs (guild_id, kind, payload_json, due_at, created_at) "
            "VALUES (?,?,?,?,?)",
            (guild_id, kind, json.dumps(payload, default=str), iso(due_at), iso(utcnow())))

    def due_jobs(self, now: datetime | None = None) -> list[sqlite3.Row]:
        now = now or utcnow()
        return self.query_all(
            "SELECT * FROM scheduled_jobs WHERE status='pending' AND due_at<=? ORDER BY due_at",
            (iso(now),))

    def mark_job(self, job_id: int, status: str, error: str | None = None) -> None:
        self.execute("UPDATE scheduled_jobs SET status=?, error=? WHERE id=?",
                     (status, error, job_id))

    def pending_job_count(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS n FROM scheduled_jobs WHERE status='pending'")
        return int(row["n"]) if row else 0

    # ---- votes ------------------------------------------------------
    def create_vote(self, *, guild_id: int, target_id: int, reporter_id: int, reason: str,
                    judge: dict | None, deadline_at: datetime | None,
                    channel_id: int | None = None, target_name: str | None = None,
                    reporter_name: str | None = None) -> int:
        return self.execute(
            "INSERT INTO votes (guild_id, channel_id, target_id, reporter_id, "
            "target_name, reporter_name, reason, "
            "judge_json, deadline_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (guild_id, channel_id, target_id, reporter_id,
             target_name, reporter_name, reason,
             json.dumps(judge, default=str) if judge else None,
             iso(deadline_at) if deadline_at else None, iso(utcnow())))

    def get_vote(self, vote_id: int) -> sqlite3.Row | None:
        return self.query_one("SELECT * FROM votes WHERE id=?", (vote_id,))

    def set_vote_message(self, vote_id: int, *, channel_id: int, message_id: int) -> None:
        self.execute("UPDATE votes SET channel_id=?, message_id=? WHERE id=?",
                     (channel_id, message_id, vote_id))

    def close_vote(self, vote_id: int, *, status: str, action: str | None = None,
                   ai_verdict: str | None = None, ai_note: str | None = None) -> None:
        self.execute("UPDATE votes SET status=?, action=?, ai_verdict=?, ai_note=?, "
                     "closed_at=? WHERE id=?",
                     (status, action, ai_verdict, ai_note, iso(utcnow()), vote_id))

    def list_open_votes(self, guild_id: int | None = None) -> list[sqlite3.Row]:
        if guild_id:
            return self.query_all(
                "SELECT * FROM votes WHERE status='open' AND guild_id=? ORDER BY id DESC",
                (guild_id,))
        return self.query_all("SELECT * FROM votes WHERE status='open' ORDER BY id DESC")

    def list_votes(self, *, guild_id: int | None = None, limit: int = 50) -> list[sqlite3.Row]:
        if guild_id:
            return self.query_all(
                "SELECT * FROM votes WHERE guild_id=? ORDER BY id DESC LIMIT ?",
                (guild_id, limit))
        return self.query_all("SELECT * FROM votes ORDER BY id DESC LIMIT ?", (limit,))

    def active_vote_exists(self, *, guild_id: int, reporter_id: int, target_id: int) -> bool:
        row = self.query_one(
            "SELECT id FROM votes WHERE guild_id=? AND reporter_id=? AND target_id=? "
            "AND status='open' LIMIT 1", (guild_id, reporter_id, target_id))
        return row is not None

    def add_ballot(self, *, vote_id: int, user_id: int, choice: str) -> None:
        self.execute(
            "INSERT INTO vote_ballots (vote_id, user_id, choice, created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(vote_id, user_id) DO UPDATE SET choice=excluded.choice, "
            "created_at=excluded.created_at",
            (vote_id, user_id, choice, iso(utcnow())))

    def ballot_counts(self, vote_id: int) -> dict[str, int]:
        rows = self.query_all(
            "SELECT choice, COUNT(*) AS n FROM vote_ballots WHERE vote_id=? GROUP BY choice",
            (vote_id,))
        return {r["choice"]: int(r["n"]) for r in rows}

    def ballot_total(self, vote_id: int) -> int:
        row = self.query_one("SELECT COUNT(*) AS n FROM vote_ballots WHERE vote_id=?", (vote_id,))
        return int(row["n"]) if row else 0

    # ---- owners -----------------------------------------------------
    def add_owner(self, *, guild_id: int, subject_id: int, kind: str,
                  added_by: int | None = None) -> None:
        self.execute(
            "INSERT OR REPLACE INTO owners (guild_id, subject_id, kind, added_by, created_at) "
            "VALUES (?,?,?,?,?)",
            (guild_id, subject_id, kind, added_by, iso(utcnow())))

    def remove_owner(self, *, guild_id: int, subject_id: int, kind: str) -> None:
        self.execute("DELETE FROM owners WHERE guild_id=? AND subject_id=? AND kind=?",
                     (guild_id, subject_id, kind))

    def list_owners(self, guild_id: int) -> list[sqlite3.Row]:
        return self.query_all("SELECT * FROM owners WHERE guild_id=? ORDER BY kind, subject_id",
                              (guild_id,))

    # ---- caps / exemptions ------------------------------------------
    def set_cap(self, *, guild_id: int, role_id: int, capability: str) -> None:
        self.execute(
            "INSERT OR IGNORE INTO role_caps (guild_id, role_id, capability) VALUES (?,?,?)",
            (guild_id, role_id, capability))

    def clear_caps(self, *, guild_id: int, role_id: int) -> None:
        self.execute("DELETE FROM role_caps WHERE guild_id=? AND role_id=?", (guild_id, role_id))

    def list_caps(self, guild_id: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT role_id, capability FROM role_caps WHERE guild_id=? "
            "ORDER BY role_id, capability", (guild_id,))

    def role_caps(self, *, guild_id: int, role_ids: Iterable[int]) -> set[str]:
        ids = list(role_ids)
        if not ids:
            return set()
        marks = ",".join("?" for _ in ids)
        rows = self.query_all(
            f"SELECT capability FROM role_caps WHERE guild_id=? AND role_id IN ({marks})",
            [guild_id, *ids])
        return {r["capability"] for r in rows}

    def add_exemption(self, *, guild_id: int, subject_id: int, kind: str, scope: str) -> None:
        self.execute(
            "INSERT OR IGNORE INTO exemptions (guild_id, subject_id, kind, scope, created_at) "
            "VALUES (?,?,?,?,?)",
            (guild_id, subject_id, kind, scope, iso(utcnow())))

    def remove_exemption(self, *, guild_id: int, subject_id: int, kind: str, scope: str) -> None:
        self.execute(
            "DELETE FROM exemptions WHERE guild_id=? AND subject_id=? AND kind=? AND scope=?",
            (guild_id, subject_id, kind, scope))

    def list_exemptions(self, guild_id: int) -> list[sqlite3.Row]:
        return self.query_all("SELECT * FROM exemptions WHERE guild_id=?", (guild_id,))

    # ---- judge accounting -------------------------------------------
    def record_judge_call(self, *, layer: str, model: str | None, ok: bool,
                          input_tokens: int = 0, latency_ms: int = 0,
                          error: str | None = None) -> None:
        self.execute(
            "INSERT INTO judge_calls (layer, model, ok, input_tokens, latency_ms, error, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (layer, model, 1 if ok else 0, input_tokens, latency_ms,
             (error or "")[:300] or None, iso(utcnow())))

    def judge_stats(self, *, hours: int = 24) -> dict:
        since = iso(utcnow() - timedelta(hours=hours))
        total = self.query_one(
            "SELECT COUNT(*) AS n, COALESCE(SUM(input_tokens),0) AS tok, "
            "COALESCE(AVG(latency_ms),0) AS lat FROM judge_calls WHERE created_at>=?",
            (since,))
        ok = self.query_one(
            "SELECT COUNT(*) AS n FROM judge_calls WHERE created_at>=? AND ok=1", (since,))
        by_layer = self.query_all(
            "SELECT layer, COUNT(*) AS n FROM judge_calls WHERE created_at>=? GROUP BY layer",
            (since,))
        recent = self.query_all(
            "SELECT latency_ms, input_tokens, created_at FROM judge_calls "
            "WHERE created_at>=? ORDER BY id DESC LIMIT 40", (since,))
        n = int(total["n"]) if total else 0
        tokens = int(total["tok"]) if total else 0
        return {
            "calls": n,
            "ok": int(ok["n"]) if ok else 0,
            "tokens": tokens,
            "avg_latency_ms": int(total["lat"]) if total else 0,
            "est_cost_usd": round(tokens * 0.042 / 1_000_000, 6),
            "by_layer": {r["layer"]: int(r["n"]) for r in by_layer},
            "recent_latencies": [int(r["latency_ms"]) for r in reversed(recent)],
            "recent_tokens": [int(r["input_tokens"]) for r in reversed(recent)],
        }

    def last_judge_error(self) -> str | None:
        row = self.query_one(
            "SELECT error FROM judge_calls WHERE ok=0 AND error IS NOT NULL "
            "ORDER BY id DESC LIMIT 1")
        return row["error"] if row else None
