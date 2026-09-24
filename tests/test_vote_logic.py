"""Vote tally / verdict math - boundary cases."""
from tsabot.vote_logic import tally, verdict, winner


def test_tally_counts_known_choices_only():
    assert tally(["mute", "mute", "disconnect", "junk"]) == {
        "mute": 2, "disconnect": 1, "none": 0}


def test_winner_basic():
    assert winner({"mute": 3, "disconnect": 1, "none": 0}) == "mute"
    assert winner({"mute": 0, "disconnect": 0, "none": 4}) == "none"
    assert winner({"mute": 0, "disconnect": 0, "none": 0}) is None


def test_winner_tie_breaks_toward_milder():
    # 2-2 tie mute vs disconnect -> mute (time-bounded)
    assert winner({"mute": 2, "disconnect": 2, "none": 0}) == "mute"
    # none ties with mute -> none is mildest
    assert winner({"mute": 1, "disconnect": 0, "none": 1}) == "none"


def test_verdict_below_min_votes_fails():
    status, action = verdict({"mute": 4, "disconnect": 0, "none": 0},
                             min_votes=5, pct=0.6)
    assert status == "failed" and action is None


def test_verdict_min_votes_exactly_passes():
    status, action = verdict({"mute": 5, "disconnect": 0, "none": 0},
                             min_votes=5, pct=0.6)
    assert status == "passed" and action == "mute"


def test_verdict_share_below_pct_fails():
    status, action = verdict({"mute": 3, "disconnect": 2, "none": 1},
                             min_votes=5, pct=0.6)
    assert status == "failed" and action is None


def test_verdict_share_exactly_at_pct_passes():
    status, action = verdict({"mute": 6, "disconnect": 2, "none": 2},
                             min_votes=5, pct=0.6)
    assert status == "passed" and action == "mute"


def test_verdict_plain_none_majority_fails():
    status, action = verdict({"mute": 2, "disconnect": 0, "none": 8},
                             min_votes=5, pct=0.6)
    assert status == "failed" and action is None


def test_verdict_disconnect_passes():
    status, action = verdict({"mute": 1, "disconnect": 7, "none": 1},
                             min_votes=5, pct=0.6)
    assert status == "passed" and action == "disconnect"
