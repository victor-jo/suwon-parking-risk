# Tests for place-text cleanup and the geocoder's fallback order using a fake Kakao client
import httpx

from suwon_parking.geocode import KakaoGeocoder, split_place


def test_split_place_drops_repeated_dong_notes_and_relative_words():
    assert split_place("인계동 인계동 교동짬뽕 앞") == ("인계동", "교동짬뽕")
    assert split_place("고등동 61-142 (소화전 주변 5m 이내)") == ("고등동", "61-142")
    assert split_place("인계동 시드니볼링장 맞은편") == ("인계동", "시드니볼링장")
    assert split_place("우만1동 우만초등학교 정문 앞 삼거리") == ("우만1동", "우만초등학교 삼거리")
    assert split_place("경기도수원시권선구평동 수원시 권선구 평동 38") == ("평동", "38")
    assert split_place("영통구 영통동 1012-1") == ("영통동", "1012-1")
    assert split_place("인계동 수원시청역 7번출구") == ("인계동", "수원시청역 7번출구")
    assert split_place("매산동 팅스몰 주차장 출구 옆") == ("매산동", "팅스몰 주차장")


def test_leading_lot_number_wins_over_trailing_words(tmp_path):
    assert _geocoder(tmp_path, []).resolve("인계동 1124 소화전").precision == "address"


def _geocoder(tmp_path, keyword_docs):
    def handler(req: httpx.Request) -> httpx.Response:
        q = req.url.params["query"]
        if req.url.path.endswith("address.json"):
            docs = [{"x": "127.03", "y": "37.26", "address_name": q}] if q in ("수원시 인계동", "수원시 인계동 1124") else []
        else:
            docs = keyword_docs
        return httpx.Response(200, json={"documents": docs})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return KakaoGeocoder("k", tmp_path / "cache.jsonl", client=client)


def test_resolve_prefers_address_then_landmark_then_dong(tmp_path):
    near = [
        {"x": "127.031", "y": "37.262", "place_name": "다른가게", "address_name": "경기 수원시 팔달구 인계동 1"},
        {"x": "127.031", "y": "37.262", "place_name": "교동짬뽕", "address_name": "경기 수원시 팔달구 인계동 2"},
    ]
    g = _geocoder(tmp_path, near)
    assert g.resolve("인계동 1124").precision == "address"
    assert g.resolve("인계동 교동짬뽕 앞").matched == "교동짬뽕"

    far = [{"x": "127.30", "y": "37.50", "place_name": "교동짬뽕", "address_name": "서울 강남구 역삼동 1"}]
    assert _geocoder(tmp_path, far).resolve("인계동 교동짬뽕 앞").precision == "dong"


def test_dong_stem_does_not_match_the_gu_name(tmp_path):
    # '인계' is the stem of 인계동; a far hit in a '인계구' must not be accepted on the name alone.
    far = [{"x": "127.30", "y": "37.50", "place_name": "교동짬뽕", "address_name": "경기 수원시 인계구 원천동 1"}]
    assert _geocoder(tmp_path, far).resolve("인계동 교동짬뽕 앞").precision == "dong"


def test_junction_named_after_dong_falls_back_to_dong(tmp_path):
    assert _geocoder(tmp_path, []).resolve("인계동 인계동사거리").precision == "dong"


def test_geocode_caches_results(tmp_path):
    g = _geocoder(tmp_path, [])
    g.geocode(["인계동 1124"])
    again = KakaoGeocoder("k", tmp_path / "cache.jsonl", client=g.client)
    assert again.cache["인계동 1124"].precision == "address"


def test_split_place_for_seongnam_road_first_and_glued_texts():
    from suwon_parking.geocode import SEONGNAM

    assert split_place("수정구 성남동 광명로 KR모터스 주변", SEONGNAM) == ("성남동", "광명로 KR모터스")
    assert split_place("황새울로342번길 서현역 부근", SEONGNAM) == ("", "황새울로342번길 서현역")
    assert split_place("야탑역 4번출구 앞", SEONGNAM) == ("", "야탑역 4번출구")
    assert split_place("판교로210길미르어린이공원주변", SEONGNAM) == ("", "판교로210길 미르어린이공원")
    assert split_place("판교공원로 성남시판교도서관 주변", SEONGNAM) == ("", "판교공원로 성남시판교도서관")
    assert split_place("그랑메종408동건너편(하원초교부근)", SEONGNAM) == ("", "그랑메종408동")


def _seongnam(tmp_path, keyword_docs):
    from suwon_parking.geocode import SEONGNAM

    roads = {"성남시 황새울로342번길": ("127.120", "37.385"), "성남시 성남동": ("127.150", "37.430")}

    def handler(req: httpx.Request) -> httpx.Response:
        q = req.url.params["query"]
        if req.url.path.endswith("address.json"):
            docs = [{"x": roads[q][0], "y": roads[q][1], "address_name": q}] if q in roads else []
        else:
            docs = keyword_docs
        return httpx.Response(200, json={"documents": docs})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return KakaoGeocoder("k", tmp_path / "cache.jsonl", client=client, city=SEONGNAM)


def test_seongnam_leading_road_anchors_landmark_search_and_falls_back_to_road(tmp_path):
    near = [{"x": "127.123", "y": "37.384", "place_name": "서현역 수인분당선", "address_name": "경기 성남시 분당구 서현동 1"}]
    assert _seongnam(tmp_path, near).resolve("황새울로342번길 서현역 부근").matched == "서현역 수인분당선"
    far = [{"x": "127.30", "y": "37.50", "place_name": "서현역", "address_name": "경기 성남시 분당구 서현동 1"}]
    g = _seongnam(tmp_path, far).resolve("황새울로342번길 서현역 부근")
    assert (g.precision, g.lon, g.matched) == ("road", 127.12, "황새울로342번길")


def test_seongnam_unanchored_landmark_must_be_in_the_city(tmp_path):
    docs = [{"x": "127.0", "y": "37.5", "place_name": "야탑역 4번출구", "address_name": "서울 강남구 역삼동 1"},
            {"x": "127.127", "y": "37.411", "place_name": "야탑역 4번출구", "address_name": "경기 성남시 분당구 야탑동 1"}]
    assert _seongnam(tmp_path, docs).resolve("야탑역 4번출구 앞").lon == 127.127
    assert _seongnam(tmp_path, docs[:1]).resolve("야탑역 4번출구 앞").precision == "none"


def test_seongnam_dong_road_landmark_searches_landmark_without_the_road(tmp_path):
    docs = [{"x": "127.151", "y": "37.431", "place_name": "홍콩중화요리", "address_name": "경기 성남시 중원구 성남동 1"}]
    assert _seongnam(tmp_path, docs).resolve("성남동 광명로 홍콩중화요리 주변").matched == "홍콩중화요리"


def test_lot_number_without_dong_is_not_looked_up(tmp_path):
    assert _seongnam(tmp_path, []).resolve("93-1 부근").precision == "none"


def test_seongnam_far_landmark_on_the_same_road_is_accepted(tmp_path):
    # Long roads: the road's representative point can be kilometres from the landmark.
    docs = [{"x": "127.30", "y": "37.50", "place_name": "서현역", "address_name": "경기 성남시 분당구 서현동 1",
             "road_address_name": "경기 성남시 분당구 황새울로 360"}]
    assert _seongnam(tmp_path, docs).resolve("황새울로342번길 서현역 부근").precision == "landmark"


def test_split_place_for_gwacheon_full_lot_addresses():
    from suwon_parking.geocode import GWACHEON

    assert split_place("경기도 과천시 별양동 1-27", GWACHEON) == ("별양동", "1-27")
    assert split_place("경기도 과천시 원문동 10(코오롱타워 인근)", GWACHEON) == ("원문동", "10")
    assert split_place("경기도 과천시 갈현동 인덕원방면", GWACHEON) == ("갈현동", "인덕원")


def test_unknown_lot_number_is_not_searched_as_a_shop_name(tmp_path):
    # '갈현동 25' must not become 'GS25' when the address lookup finds nothing.
    shop = [{"x": "127.031", "y": "37.262", "place_name": "GS25 인계점", "address_name": "경기 수원시 팔달구 인계동 1"}]
    assert _geocoder(tmp_path, shop).resolve("인계동 25").precision == "dong"
    assert _geocoder(tmp_path, shop).resolve("인계동 인계로 25").precision == "dong"


def test_far_lot_in_a_large_legal_dong_is_accepted_when_the_address_names_it(tmp_path):
    from suwon_parking.geocode import ANYANG

    found = {"안양시 호계동": ("126.957", "37.375", "경기 안양시 동안구 호계동"),
             "안양시 호계동 1013": ("126.945", "37.386", "경기 안양시 동안구 호계동 1013"),  # ~1.7 km away
             "안양시 비산동 1": ("127.30", "37.50", "서울 강남구 역삼동 1")}

    def handler(req: httpx.Request) -> httpx.Response:
        q = req.url.params["query"]
        hit = found.get(q) if req.url.path.endswith("address.json") else None
        return httpx.Response(200, json={"documents": [{"x": hit[0], "y": hit[1], "address_name": hit[2]}] if hit else []})

    g = KakaoGeocoder("k", tmp_path / "c.jsonl", client=httpx.Client(transport=httpx.MockTransport(handler)), city=ANYANG)
    assert g.resolve("호계동 1013").precision == "address"
    found["안양시 비산동"] = ("126.94", "37.40", "경기 안양시 동안구 비산동")
    assert g.resolve("비산동 1").precision == "dong"  # far and in another city: still rejected
