"""Config loading + validation."""
import pathlib

import pytest

from tsabot.config import ConfigError, load_config


def test_defaults_with_empty_env(tmp_path):
    cfg = load_config(env={}, base=tmp_path)
    assert cfg.dry_run is True                    # public default: dry-run first
    assert cfg.spam_timeout_minutes == 10
    assert cfg.vote_min == 5
    assert abs(cfg.vote_pct - 0.6) < 1e-9
    assert cfg.vote_minutes == 10


def test_env_file_parsing(tmp_path):
    (tmp_path / ".env").write_text(
        "DISCORD_TOKEN=tok123\nDISCORD_GUILD_ID=42\nDRY_RUN=0\nVOTE_MIN=7\n", encoding="utf-8")
    cfg = load_config(env={}, base=tmp_path)
    assert cfg.discord_token == "tok123"
    assert cfg.guild_id == 42
    assert cfg.dry_run is False
    assert cfg.vote_min == 7


def test_process_env_overrides_file(tmp_path):
    (tmp_path / ".env").write_text("DISCORD_GUILD_ID=1\n", encoding="utf-8")
    cfg = load_config(env={"DISCORD_GUILD_ID": "2"}, base=tmp_path)
    assert cfg.guild_id == 2


def test_owner_ids_parsing():
    cfg = load_config(env={"OWNER_IDS": "111,222;333"}, base=pathlib.Path("."))
    assert cfg.owner_ids == frozenset({111, 222, 333})


def test_bot_errors_are_actionable(tmp_path):
    # hermetic: empty env file + empty env dict, so the real .env can't leak in
    cfg = load_config(env={}, base=tmp_path)
    errs = cfg.bot_errors()
    assert len(errs) == 2
    assert any("DISCORD_TOKEN" in e for e in errs)
    assert any("DISCORD_GUILD_ID" in e for e in errs)
    with pytest.raises(ConfigError):
        cfg.require_bot()


def test_bad_numbers_fall_back_to_defaults():
    cfg = load_config(env={"VOTE_MIN": "abc", "VOTE_PCT": "x"}, base=pathlib.Path("."))
    assert cfg.vote_min == 5
    assert abs(cfg.vote_pct - 0.6) < 1e-9


def test_snowflake_ids_survive_float_precision(tmp_path):
    """Discord snowflakes (~1.5e18) exceed float64 precision (2^53).
    int(float(s)) corrupts them — this caused a live bot to see guild
    1000000000000000001 as ...0971136 and silently ignore every message."""
    (tmp_path / ".env").write_text(
        "DISCORD_GUILD_ID=1000000000000000001\n"
        "OWNER_IDS=2000000000000000001,3000000000000000001\n"
        "TEST_CHANNEL_ID=3000000000000000003\n", encoding="utf-8")
    cfg = load_config(env={}, base=tmp_path)
    assert cfg.guild_id == 1000000000000000001
    assert cfg.owner_ids == frozenset({2000000000000000001, 3000000000000000001})
    assert cfg.test_channel_id == 3000000000000000003
    # and the proof of the old bug:
    assert int(float("1000000000000000001")) != 1000000000000000001


def test_decimal_strings_still_parse(tmp_path):
    (tmp_path / ".env").write_text("VOTE_MIN=3.0\n", encoding="utf-8")
    cfg = load_config(env={}, base=tmp_path)
    assert cfg.vote_min == 3
