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


def test_attach_recent_counts_report_days_near_exact_points_only():
    from datetime import date

    from suwon_parking.points import Point, attach_recent
    from suwon_parking.records import Report

    near = Point(127.0, 37.0, "address", "near", "near", "patrol", 1, 0.1, [0] * 168)
    rough = Point(127.0, 37.0, "dong", "rough", "rough", "patrol", 1, 0.1, [0] * 168)
    far = Point(127.01, 37.0, "cctv", "far", "far", "cctv", 1, 0.1, [0] * 168)  # ~890 m east
    geo = {
        "a": Geo("a", 127.0005, 37.0, "address", "a"),  # ~45 m from 'near'
        "b": Geo("b", 127.0, 37.0, "dong", "b"),  # vague report location: ignored
    }
    reports = [Report(date(2025, 9, 1), "팔달구", "a"), Report(date(2025, 9, 1), "팔달구", "a"),
               Report(date(2025, 9, 2), "팔달구", "a"), Report(date(2025, 9, 3), "팔달구", "b")]
    attach_recent([near, rough, far], reports, geo, radius_km=0.1)
    assert (near.recent, rough.recent, far.recent) == (2, 0, 0)


def test_attach_recent_finds_reports_just_inside_radius_east_and_west():
    from datetime import date

    from suwon_parking.points import Point, attach_recent
    from suwon_parking.records import Report

    # At latitude 37.27 one degree of longitude is about 88 km, so 0.00107 deg is about 95 m.
    # Points sit 1 km apart (no shared reports) and sweep every offset within a grid bucket.
    pts = [Point(127.0 + i * 0.01 + i * 0.00005, 37.27, "address", str(i), str(i), "patrol", 1, 0.1, [0] * 168)
           for i in range(20)]
    geo = {}
    reports = []
    for i, p in enumerate(pts):
        for day, side, off in ((1, "e", 0.00107), (2, "w", -0.00107)):
            name = f"{i}{side}"
            geo[name] = Geo(name, p.lon + off, p.lat, "address", name)
            reports.append(Report(date(2025, 9, day), "팔달구", name))
    attach_recent(pts, reports, geo, radius_km=0.1)
    assert [p.recent for p in pts] == [2] * len(pts)


def test_summarize_without_hours_leaves_grid_empty_and_reads_camera_variants():
    # Seongnam: dates only, and fixed cameras are labelled '고정형CCTV'.
    geo = {"A": Geo("A", 127.0, 37.0, "address", "A")}
    records = [_r("2025-01-01 00:00:00", "A", "고정형CCTV"), _r("2025-01-02 00:00:00", "A", "고정형CCTV")]
    (a,) = summarize(records, geo, hours=False)
    assert (a.kind, a.day_share, sum(a.grid)) == ("cctv", 1.0, 0)
