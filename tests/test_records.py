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


def test_parse_accepts_unpadded_and_mangled_12_hour_times():
    raw = _csv(
        "2021,수원시,권선구청,2021-06-24 9:24,고색동 산업로,주행형CCTV,2026-04-24",
        "2024,수원시,권선구청,2024-03-19  2:409:06 PM,산업로92번길,주행형CCTV,2026-04-24",
        "2024,수원시,권선구청,2024-04-05  10:509:17 AM,산업로,주행형CCTV,2026-04-24",
        "2024,수원시,권선구청,2024-05-29  12:109:52 PM,고색동 921,안전신문고,2026-04-24",
        "2024,수원시,권선구청,2024-09-04  2:3009:55 PM,산업로92번길 94-20,주행형CCTV,2026-04-24",
    )
    got = [(r.at.hour, r.at.minute) for r in parse_enforcements(raw)]
    assert got == [(9, 24), (14, 40), (10, 50), (12, 10), (14, 30)]


def test_parse_reports_reads_date_only_rows_and_cleans_place():
    from datetime import date

    from suwon_parking.records import parse_reports

    raw = (
        "연도,시군명,관리기관명,단속일시정보,단속장소,단속방법,과태료부과,데이터기준일자\n"
        "2025,수원시,장안구,2025-09-03,율전동 395-6,안전신문고,40000 ,2025-11-30\n"
        "2025,수원시,팔달구,2025-09-04,인계동 1098\t횡단보도,안전신문고,40000 ,2025-11-30\n"
        "2025,수원시,영통구 ,2025-09-05, ,안전신문고,40000 ,2025-11-30\n"
    ).encode("cp949")
    got = [(r.day, r.office, r.place) for r in parse_reports(raw)]
    assert got == [(date(2025, 9, 3), "장안구", "율전동 395-6"), (date(2025, 9, 4), "팔달구", "인계동 1098 횡단보도")]


def test_parse_reads_utf8_bom_file_with_date_only_times():
    # Seongnam's file: UTF-8 with BOM, no data-date column, dates with no time or a placeholder '0:00'.
    raw = (
        "집계년도,시군명,관리기관명,단속일시정보,단속장소,단속방법\n"
        "2025,성남시,성남시 수정구,2025-01-01, 산성대로 대기가스,고정형CCTV\n"
        "2025,성남시,성남시 중원구,2025-05-30 0:00, 성남동 광명로,PDA\n"
    ).encode("utf-8-sig")
    got = [(r.at.isoformat(), r.office, r.place, r.method) for r in parse_enforcements(raw)]
    assert got == [("2025-01-01T00:00:00", "성남시 수정구", "산성대로 대기가스", "고정형CCTV"),
                   ("2025-05-30T00:00:00", "성남시 중원구", "성남동 광명로", "PDA")]


def test_parse_gwacheon_reports_reads_its_own_columns():
    from suwon_parking.records import parse_gwacheon

    raw = (
        "연번,단속일시,단속행정동,단속위치,과태료부과여부\n"
        "1,2024-01-01 11:26,중앙동,경기도 과천시 중앙동 59,Y\n"
        "2,2024-01-02 9:05,갈현동, ,Y\n"
    ).encode("cp949")
    got = [(r.at.isoformat(), r.office, r.place, r.method) for r in parse_gwacheon(raw)]
    assert got == [("2024-01-01T11:26:00", "중앙동", "경기도 과천시 중앙동 59", "안전신문고")]
