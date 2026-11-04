# Tests for merging places into points and the per-weekday/hour day rate
from datetime import date, datetime

from suwon_parking.aggregate import aggregate, weekday_totals
from suwon_parking.geocode import Geo
from suwon_parking.records import Enforcement


def _r(ts: str, place: str) -> Enforcement:
    return Enforcement(datetime.fromisoformat(ts), "팔달구청", place, "고정형")


def test_weekday_totals_counts_each_weekday_in_range():
    # 2024-01-01 is a Monday; two full weeks.
    assert weekday_totals(date(2024, 1, 1), date(2024, 1, 14)) == [2] * 7


def test_aggregate_merges_same_point_and_computes_day_rate():
    geo = {
        "A 앞": Geo("A 앞", 127.0, 37.0, "landmark", "A"),
        "A 맞은편": Geo("A 맞은편", 127.0, 37.0, "landmark", "A"),
        "모름": Geo("모름", None, None, "none"),
    }
    records = [
        _r("2024-01-01 14:05:00", "A 앞"),
        _r("2024-01-01 14:40:00", "A 맞은편"),  # same Monday 14h → same day
        _r("2024-01-08 14:10:00", "A 앞"),  # second Monday
        _r("2024-01-14 09:00:00", "모름"),  # dropped: no coordinates
    ]
    cells = aggregate(records, geo)
    assert len(cells) == 1
    c = cells[0]
    assert (c.weekday, c.hour, c.count, c.days) == (0, 14, 3, 2)
    assert c.day_rate == 1.0  # both Mondays in the period had an enforcement
    assert c.places.startswith("A 앞")
    assert c.method == "고정형"


def test_dong_level_places_are_not_merged_onto_the_dong_centre():
    geo = {
        "매산동 X": Geo("매산동 X", 127.0, 37.0, "dong", "매산동"),
        "매산동 Y": Geo("매산동 Y", 127.0, 37.0, "dong", "매산동"),
    }
    cells = aggregate([_r("2024-01-01 14:00:00", "매산동 X"), _r("2024-01-01 14:00:00", "매산동 Y")], geo)
    assert sorted(c.places for c in cells) == ["매산동 X", "매산동 Y"]
