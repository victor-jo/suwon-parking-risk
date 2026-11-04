# Tests for the per-point summary that feeds the map
from datetime import datetime

from suwon_parking.geocode import Geo
from suwon_parking.points import summarize
from suwon_parking.records import Enforcement


def _r(ts: str, place: str, method: str = "고정형") -> Enforcement:
    return Enforcement(datetime.fromisoformat(ts), "팔달구청", place, method)


def test_summarize_merges_point_and_reports_day_share_kind_and_grid():
    geo = {
        "A 앞": Geo("A 앞", 127.0, 37.0, "cctv", "인계동 A"),
        "A 맞은편": Geo("A 맞은편", 127.0, 37.0, "landmark", "A"),
        "B": Geo("B", 127.1, 37.1, "road", "B로"),
    }
    records = [
        _r("2024-01-01 14:05:00", "A 앞"),  # Monday
        _r("2024-01-01 14:40:00", "A 맞은편"),  # same day
        _r("2024-01-03 09:00:00", "B", "주행형"),
        _r("2024-01-04 09:00:00", "A 앞", "국민신문고"),  # Thursday; period ends here (4 days)
    ]
    a, b = sorted(summarize(records, geo), key=lambda p: p.lon)
    assert (a.label, a.count, a.kind, a.precision) == ("인계동 A", 3, "cctv", "cctv")
    assert a.day_share == 0.5  # 2 of the 4 days in the period
    assert a.grid[0 * 24 + 14] == 100  # the only Monday had enforcement at 14h
    assert a.grid[3 * 24 + 9] == 100
    assert sum(a.grid) == 200
    assert (b.label, b.kind, b.day_share, b.places) == ("B", "patrol", 0.25, "B")  # road: place text, not "B로"


def test_points_are_sorted_by_day_share():
    geo = {p: Geo(p, 127.0 + i, 37.0, "address", p) for i, p in enumerate(["X", "Y"])}
    records = [_r("2024-01-01 10:00:00", "X"), _r("2024-01-01 10:00:00", "Y"), _r("2024-01-02 10:00:00", "Y")]
    assert [p.label for p in summarize(records, geo)] == ["Y", "X"]
