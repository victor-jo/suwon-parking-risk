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


def test_junction_named_after_dong_falls_back_to_dong(tmp_path):
    assert _geocoder(tmp_path, []).resolve("인계동 인계동사거리").precision == "dong"


def test_geocode_caches_results(tmp_path):
    g = _geocoder(tmp_path, [])
    g.geocode(["인계동 1124"])
    again = KakaoGeocoder("k", tmp_path / "cache.jsonl", client=g.client)
    assert again.cache["인계동 1124"].precision == "address"
