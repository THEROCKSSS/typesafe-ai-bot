"""Configuration loading for TypeSafe AI Bot.

Loads from a .env file plus the process environment (environment wins).
Missing critical values produce clear, actionable errors instead of tracebacks.
"""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field


class ConfigError(Exception):
    """Raised when required configuration is missing or malformed."""


def _parse_env_file(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    """Parse an int WITHOUT float round-trip.

    Discord snowflakes (~1.5e18) exceed float64 precision (2^53): int(float(s))
    silently corrupts them (1000000000000000001 -> ...0971136). Plain digit
    strings must be parsed directly.
    """
    if value is None or value.strip() == "":
        return default
    v = value.strip()
    try:
        if v.lstrip("+-").isdigit():
            return int(v)
        return int(float(v))  # only for genuinely decimal values like "3.0"
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def _ids(value: str | None) -> frozenset[int]:
    if not value:
        return frozenset()
    out: set[int] = set()
    for chunk in value.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            out.add(int(chunk))
    return frozenset(out)


def _opt_id(value: str | None) -> int | None:
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


@dataclass
class Config:
    # Discord
    discord_token: str = ""
    guild_id: int = 0
    owner_ids: frozenset[int] = field(default_factory=frozenset)
    # Behaviour
    dry_run: bool = False
    data_dir: pathlib.Path = pathlib.Path("data")
    db_path: pathlib.Path = pathlib.Path("data/tsabot.db")
    rules_path: pathlib.Path = pathlib.Path("policy/rules.json")
    # Channels / roles
    reports_channel_id: int | None = None
    mod_log_channel_id: int | None = None
    vote_role_id: int | None = None
    # Spam
    spam_timeout_minutes: int = 10
    # Votes
    vote_min: int = 5
    vote_pct: float = 0.6
    vote_minutes: int = 10
    # Notification routing: "log" (default), "dm", "both"
    notify_mode: str = "log"
    # Reports
    report_daily_cap: int = 5
    report_min_len: int = 12
    report_invalid_limit: int = 3  # invalid reports in 7 days -> reporting rights revoked
    # Automod bands
    automod_high: float = 0.85
    automod_medium: float = 0.60
    report_valid_high: float = 0.75
    report_valid_medium: float = 0.45
    # Judge
    jev_model: str = "jev-latest"
    typesafe_api_key: str = ""
    opencode_zen_api_key: str = ""
    judge_max_per_min: int = 60
    # Dashboard
    dashboard_port: int = 8788
    # Testing (webhook-driven detection tests)
    test_channel_id: int | None = None
    test_webhook_id: int | None = None

    # ---- validation -------------------------------------------------
    def bot_errors(self) -> list[str]:
        """Errors that block running the Discord bot."""
        errs: list[str] = []
        if not self.discord_token:
            errs.append("DISCORD_TOKEN is missing — create a Discord app, enable the "
                        "Message Content + Server Members intents, and paste the bot token into .env")
        if not self.guild_id:
            errs.append("DISCORD_GUILD_ID is missing — right-click your server (Developer Mode on) "
                        "and Copy Server ID")
        return errs

    def require_bot(self) -> None:
        errs = self.bot_errors()
        if errs:
            raise ConfigError("Configuration is incomplete:\n  - " + "\n  - ".join(errs))

    def effective_db_path(self, base: pathlib.Path | None = None) -> pathlib.Path:
        base = base or pathlib.Path.cwd()
        p = self.db_path
        return p if p.is_absolute() else (base / p)

    def effective_rules_path(self, base: pathlib.Path | None = None) -> pathlib.Path:
        base = base or pathlib.Path.cwd()
        p = self.rules_path
        return p if p.is_absolute() else (base / p)


def load_config(env_file: str | pathlib.Path | None = None,
                env: dict[str, str] | None = None,
                base: pathlib.Path | None = None) -> Config:
    """Load config. `env` overrides values read from the env file.

    `base` is the directory relative paths resolve against (default cwd).
    """
    base = base or pathlib.Path.cwd()
    values: dict[str, str] = {}

    file_path = pathlib.Path(env_file) if env_file else (base / ".env")
    if file_path.is_file():
        values.update(_parse_env_file(file_path))

    source_env = os.environ if env is None else env
    values.update({k: v for k, v in source_env.items() if v is not None})

    cfg = Config(
        discord_token=values.get("DISCORD_TOKEN", "").strip(),
        guild_id=_int(values.get("DISCORD_GUILD_ID"), 0),
        owner_ids=_ids(values.get("OWNER_IDS")),
        dry_run=_bool(values.get("DRY_RUN"), True),
        db_path=pathlib.Path(values.get("DB_PATH", "data/tsabot.db")),
        rules_path=pathlib.Path(values.get("RULES_PATH", "policy/rules.json")),
        reports_channel_id=_opt_id(values.get("REPORTS_CHANNEL_ID")),
        mod_log_channel_id=_opt_id(values.get("MOD_LOG_CHANNEL_ID")),
        vote_role_id=_opt_id(values.get("VOTE_ROLE_ID")),
        spam_timeout_minutes=_int(values.get("SPAM_TIMEOUT_MINUTES"), 10),
        vote_min=_int(values.get("VOTE_MIN"), 5),
        vote_pct=_float(values.get("VOTE_PCT"), 0.6),
        vote_minutes=_int(values.get("VOTE_MINUTES"), 10),
        notify_mode=values.get("NOTIFY_MODE", "log").strip().lower(),
        report_daily_cap=_int(values.get("REPORT_DAILY_CAP"), 5),
        report_min_len=_int(values.get("REPORT_MIN_LEN"), 12),
        report_invalid_limit=_int(values.get("REPORT_INVALID_LIMIT"), 3),
        automod_high=_float(values.get("AUTOMOD_HIGH"), 0.85),
        automod_medium=_float(values.get("AUTOMOD_MEDIUM"), 0.60),
        report_valid_high=_float(values.get("REPORT_VALID_HIGH"), 0.75),
        report_valid_medium=_float(values.get("REPORT_VALID_MEDIUM"), 0.45),
        jev_model=values.get("JEV_MODEL", "jev-latest").strip() or "jev-latest",
        typesafe_api_key=values.get("TYPESAFE_API_KEY", "").strip(),
        opencode_zen_api_key=values.get("OPENCODE_ZEN_API_KEY", "").strip(),
        judge_max_per_min=_int(values.get("JUDGE_MAX_PER_MIN"), 60),
        dashboard_port=_int(values.get("DASHBOARD_PORT"), 8788),
        test_channel_id=_opt_id(values.get("TEST_CHANNEL_ID")),
        test_webhook_id=_opt_id(values.get("TEST_WEBHOOK_ID")),
    )
    if cfg.notify_mode not in ("dm", "log", "both"):
        cfg.notify_mode = "log"
    data_dir = cfg.db_path.parent
    cfg.data_dir = data_dir if data_dir.is_absolute() else (base / data_dir)
    return cfg
