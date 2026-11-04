# Tests for parsing the enforcement CSV and the coverage/hourly aggregations
from suwon_parking.records import hourly_counts, parse_enforcements, place_coverage

HEADER = "집계년도,시군명,관리기관명,단속일시정보,단속장소,단속방법,데이터기준일자\n"


def _csv(*lines: str) -> bytes:
    return (HEADER + "".join(l + "\n" for l in lines)).encode("cp949")


def test_parse_reads_cp949_and_skips_blank_places():
    raw = _csv(
        "2022,수원시,팔달구청,2022-01-01 14:05:00,인계동 CU 사거리,고정형,2023-12-01",
        "2022,수원시,권선구청,2022-01-01 09:00:00, ,주행형,2023-12-01",
    )
    recs = parse_enforcements(raw)
    assert len(recs) == 1
    assert (recs[0].place, recs[0].method, recs[0].at.hour) == ("인계동 CU 사거리", "고정형", 14)


def test_coverage_and_hourly_counts():
    raw = _csv(
        "2022,수원시,팔달구청,2022-01-01 14:05:00,A,고정형,2023-12-01",
        "2022,수원시,팔달구청,2022-01-02 14:30:00,A,고정형,2023-12-01",
        "2022,수원시,팔달구청,2022-01-03 09:00:00,B,보행,2023-12-01",
    )
    recs = parse_enforcements(raw)
    assert place_coverage(recs, 1) == 2 / 3
    hours = hourly_counts(recs)
    assert (hours[14], hours[9], sum(hours)) == (2, 1, 3)
