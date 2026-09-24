"""Spam detectors - boundary cases + cooldown behaviour."""
from tsabot.detectors import SpamDetector, SpamThresholds, count_mentions, has_link


def test_burst_trips_and_cools_down():
    d = SpamDetector()
    ts = 1000.0
    trips = []
    for i in range(6):
        trips += d.record(1, content_hash=f"h{i}", ts=ts + i * 0.1)
    assert any(t.kind == "burst" for t in trips)
    # cooldown: same window dropped, no immediate re-trip
    trips2 = d.record(1, content_hash="hx", ts=ts + 0.7)
    assert not any(t.kind == "burst" for t in trips2)


def test_burst_does_not_trip_below_threshold():
    d = SpamDetector()
    trips = []
    for i in range(5):
        trips += d.record(1, content_hash=f"h{i}", ts=1000.0 + i * 0.1)
    assert trips == []


def test_duplicate_trips():
    d = SpamDetector()
    trips = []
    for i in range(4):
        trips += d.record(1, content_hash="same", ts=1000.0 + i * 0.5)
    assert any(t.kind == "duplicate" for t in trips)


def test_duplicate_expires_out_of_window():
    d = SpamDetector(SpamThresholds(duplicate_window=5.0))
    trips = []
    for i in range(4):
        trips += d.record(1, content_hash="same", ts=1000.0 + i * 6.0)
    assert not any(t.kind == "duplicate" for t in trips)


def test_mass_mention_trips():
    # 3 messages x 2 mentions = 6 mentions (kept under the burst threshold so
    # the burst detector doesn't fire first and sweep the window)
    d = SpamDetector()
    trips = []
    for i in range(3):
        trips += d.record(1, content_hash=f"m{i}", mentions=2, ts=1000.0 + i * 0.5)
    assert any(t.kind == "mass_mention" for t in trips)


def test_link_flood_trips():
    d = SpamDetector()
    trips = []
    for i in range(4):
        trips += d.record(1, content_hash=f"l{i}", has_link=True, ts=1000.0 + i)
    assert any(t.kind == "link_flood" for t in trips)


def test_independent_users_do_not_cross_trip():
    d = SpamDetector()
    trips = []
    for i in range(5):
        trips += d.record(1, content_hash=f"a{i}", ts=1000.0 + i * 0.1)
        trips += d.record(2, content_hash=f"b{i}", ts=1000.0 + i * 0.1)
    assert trips == []


def test_helpers():
    assert has_link("check https://example.com x")
    assert not has_link("no links here")
    assert count_mentions("hello", [1, 2]) == 2
    assert count_mentions("@everyone look") >= 3
    assert count_mentions("<@&123>") >= 1
