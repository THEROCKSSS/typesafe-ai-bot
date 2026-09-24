"""Degraded-mode contract tests: when the judge chain is down, heuristics may
flag for human review but must NEVER drive enforcement, votes, or dismissals."""
import pytest

from tsabot.db import Database


class FakeGuild:
    def __init__(self, gid=1):
        self.id = gid
        self.name = "Test Guild"

    def get_channel(self, cid):
        return None

    def get_role(self, rid):
        return None


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "deg.db")
    d.init()
    return d


def test_heuristic_flags_severe_only():
    from tsabot.judge import heuristic_verdicts
    severe = ["kys", "you retard", "i will dox you"]
    clean = ["gg that was fun", "we got killed in the contested zone",
             "great team-kill defense"]
    for text in severe:
        v = heuristic_verdicts({"message": {"content": text}}, ["harassment"])
        assert v["_heuristic"]["flagged"] is True, text
    for text in clean:
        v = heuristic_verdicts({"message": {"content": text}}, ["harassment"])
        assert v["_heuristic"]["flagged"] is False, text


def test_degraded_report_creates_review_case_not_invalid(db):
    """A degraded-layer report must be 'review', never 'invalid' — the reporter
    is not penalized because the judge is down."""
    db.add_case(guild_id=1, kind="report", action="review", target_id=2,
                reporter_id=7, reason="spam in vc",
                detail={"layer": "heuristic", "error": "HTTP 402"})
    assert db.invalid_report_count(guild_id=1, reporter_id=7) == 0
    rows = db.query_all("SELECT * FROM cases WHERE guild_id=? AND kind='report'", (1,))
    assert rows and rows[0]["action"] == "review"


def test_heuristic_probabilities_are_binary_not_graduated():
    """The heuristic floor reports 0.9/0.05 — it is a flag, not a judgment.
    Both values sit outside the automod action band logic that requires a Jev
    layer result, by construction."""
    from tsabot.judge import heuristic_verdicts
    hit = heuristic_verdicts({"message": {"content": "kys"}}, ["harassment"])
    miss = heuristic_verdicts({"message": {"content": "hello"}}, ["harassment"])
    assert hit["harassment"]["noul"] == pytest.approx(0.9)
    assert miss["harassment"]["noul"] == pytest.approx(0.05)
