# Tests for parsing the camera list and matching camera names to enforcement places
from suwon_parking.cctv import match_places, parse_cameras

RAW = (
    "연번,시군구,관리기관,단속구분,단속동,단속지역,위도,경도,설치일자,데이터기준일자\n"
    "1,수원시,영통구청,고정형,원천동,아주대정문삼거리,37.278595,127.043714,2010-10-30,2026-01-20\n"
).encode("cp949")


def test_match_by_dong_plus_spot_or_spot_alone():
    cams = parse_cameras(RAW)
    got = match_places(["원천동 아주대정문삼거리", "원천동 아주대 정문삼거리", "원천동 다른곳"], cams)
    assert set(got) == {"원천동 아주대정문삼거리", "원천동 아주대 정문삼거리"}
    g = got["원천동 아주대정문삼거리"]
    assert (g.precision, g.lon, g.lat) == ("cctv", 127.043714, 37.278595)
