# Tests for comparing an old enforcement pattern against a later period
from datetime import date, datetime

from suwon_parking.freshness import compare, day_rates, street_key
from suwon_parking.records import Enforcement


def _r(at: str, place: str) -> Enforcement:
    return Enforcement(datetime.fromisoformat(at), "권선구청", place, "주행형CCTV")


def test_street_key_drops_dong_prefix_and_building_number():
    assert street_key("고색동 산업로") == "산업로"
    assert street_key("산업로 85") == "산업로"
    assert street_key("고색동 고색동 982") == "982"
    assert street_key("고색동 982 횡단보도") == "982"


def test_day_rates_counts_distinct_days_per_weekday_inside_period():
    recs = [
        _r("2024-01-01 10:05", "산업로"),  # Monday
        _r("2024-01-01 10:40", "고색동 산업로"),  # same day, same cell
        _r("2024-01-08 10:00", "산업로 85"),  # next Monday
        _r("2024-01-16 10:00", "산업로"),  # outside the period
    ]
    rates = day_rates(recs, date(2024, 1, 1), date(2024, 1, 14))
    assert rates == {("산업로", 0, 10): 1.0}


def test_compare_reports_overlap_and_lift():
    old = {("a", 0, 10): 0.9, ("b", 0, 10): 0.1, ("c", 1, 15): 0.5}
    new = {("a", 0, 10): 0.8, ("b", 0, 10): 0.2, ("d", 2, 9): 0.2}
    s = compare(old, new, k=1)
    assert s["top_overlap"] == 1.0  # 'a' is the top cell in both
    assert round(s["lift"], 2) == round(0.8 / (1.2 / 4), 2)  # union has 4 cells
    assert s["corr"] > 0
