# Turns free-text enforcement places into coordinates via Kakao Local API, with a JSONL cache
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

KAKAO = "https://dapi.kakao.com/v2/local/search"
MAX_KM_FROM_DONG = 1.5


@dataclass(frozen=True, slots=True)
class City:
    name: str  # prefixed to address queries and used to cut full addresses: '수원시'
    short: str  # prefixed to keyword searches: '수원'
    center: tuple[float, float]  # lon, lat
    gus: str  # district names as a regex alternation


SUWON = City("수원시", "수원", (127.0286, 37.2636), "장안|권선|팔달|영통")
SEONGNAM = City("성남시", "성남", (127.1378, 37.4201), "수정|중원|분당")
ANYANG = City("안양시", "안양", (126.9568, 37.3943), "만안|동안")
UIWANG = City("의왕시", "의왕", (126.9683, 37.3448), "")
GUNPO = City("군포시", "군포", (126.9353, 37.3617), "")
GWACHEON = City("과천시", "과천", (126.9877, 37.4292), "")  # no districts
SUWON_CENTER = SUWON.center

# Words describing a position relative to a landmark; they only confuse search.
RELATIVE = re.compile(
    r"(맞은편|건너편|건너|앞|옆|뒤|부근|주변|인근|일대|쪽|우측|좌측|방면|"
    r"정문|후문|북문|남문|동문|서문|입구|(?<!번)출구)\d*"
)  # '7번출구' names a specific station exit, so it stays.
JUNCTION = re.compile(r"\s*(사거리|삼거리|오거리|교차로)$")
JIBUN = re.compile(r"^(산\s*)?\d+(-\d+)?$")
LEADING_JIBUN = re.compile(r"^(산\s*)?\d+(-\d+)?(?=\s|$)")
ROAD_WITH_NUMBER = re.compile(r"(로|길)\s*\d+(-\d+)?$")
ROAD_ONLY = re.compile(r"^\S+(로|길)(\d+번길)?$")
DONG = re.compile(r"[가-힣]+(\d*동|\d+가)")
# A road name glued to what follows: '판교로210길미르어린이공원'.
GLUED_ROAD = re.compile(r"([가-힣]+?(?:로|길)(?:\d+(?:번길|길))?)([가-힣A-Za-z].+)")


@dataclass(frozen=True, slots=True)
class Geo:
    place: str
    lon: float | None
    lat: float | None
    precision: str  # address | landmark | road | dong | none
    matched: str = ""


def split_place(place: str, city: City = SUWON) -> tuple[str, str]:
    """Split '인계동 인계동 교동짬뽕 앞 (메모)' into ('인계동', '교동짬뽕').

    The dong is empty when the text does not start with one ('황새울로342번길 서현역 부근').
    """
    text = re.sub(r"\(.*?\)", " ", place)
    # Full addresses ('경기도수원시권선구평동 수원시 권선구 평동 38') keep only what follows the last city/gu.
    # Only the city as an address part: '수원시청역' or '수원시립미술관' must survive.
    gu = rf"(?:{city.gus})구" if city.gus else "(?!)"  # '(?!)' never matches: a city without districts
    text = re.split(rf"{city.name}(?=\s|{gu})", text)[-1]
    text = re.sub(rf"^\s*{gu}\s+", "", text)
    tokens = text.split()
    if not tokens:
        return "", ""
    dong = tokens[0] if DONG.fullmatch(tokens[0]) else ""
    if dong:
        tokens = [t for t in tokens[1:] if t != dong]
    glued = GLUED_ROAD.fullmatch(tokens[0]) if tokens else None
    if glued:
        tokens[:1] = glued.groups()
    rest = " ".join(tokens)
    rest = RELATIVE.sub(" ", rest)
    return dong, re.sub(r"\s+", " ", rest).strip()


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = (a[0] - b[0]) * 111.0 * math.cos(math.radians(a[1]))
    dy = (a[1] - b[1]) * 111.0
    return math.hypot(dx, dy)


class KakaoGeocoder:
    def __init__(self, key: str, cache_path: Path, client: httpx.Client | None = None, city: City = SUWON):
        self.city = city
        self.client = client or httpx.Client(headers={"Authorization": f"KakaoAK {key}"}, timeout=10)
        self.cache_path = cache_path
        self.cache: dict[str, Geo] = {}
        self.dongs: dict[str, tuple[float, float] | None] = {}
        if cache_path.exists():
            for line in cache_path.open(encoding="utf-8"):
                g = Geo(**json.loads(line))
                self.cache[g.place] = g

    @classmethod
    def from_env(cls, cache_path: Path, city: City = SUWON, env_file: Path = Path(".env")) -> KakaoGeocoder:
        key = os.environ.get("KAKAO_REST_API_KEY")
        if not key and env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("KAKAO_REST_API_KEY="):
                    key = line.split("=", 1)[1].strip()
        if not key:
            raise RuntimeError("KAKAO_REST_API_KEY is not set (env or .env)")
        return cls(key, cache_path, city=city)

    def _get(self, kind: str, **params) -> list[dict]:
        resp = self.client.get(f"{KAKAO}/{kind}.json", params=params)
        resp.raise_for_status()
        return resp.json()["documents"]

    def _address(self, query: str) -> dict | None:
        docs = self._get("address", query=f"{self.city.name} {query}")
        return docs[0] if docs else None

    def _dong_center(self, dong: str) -> tuple[float, float] | None:
        if dong not in self.dongs:
            d = self._address(dong)
            self.dongs[dong] = (float(d["x"]), float(d["y"])) if d else None
        return self.dongs[dong]

    def _landmark(self, query: str, dong: str, near: tuple[float, float], anchored: bool, road: str = "") -> dict | None:
        docs = self._get(
            "keyword", query=f"{self.city.short} {query}", x=near[0], y=near[1], radius=20000, size=15, sort="accuracy"
        )
        # The hit must share the landmark's first three letters, or nearby unrelated shops win.
        head = [t for t in query.split() if t != dong][0][:3]
        docs = [d for d in docs if head in d["place_name"].replace(" ", "")]
        # Administrative dongs (영통2동) span legal dongs (영통동), so match on the name stem first.
        stem = re.sub(r"\d*동$", "", dong)
        for d in docs:
            # Compare against dong tokens only: '영통' must not match the gu name '영통구'.
            if stem and any(t.startswith(stem) and t.endswith("동") for t in d["address_name"].split()):
                return d
        # '황새울로342번길' → '황새울로': a hit on the same road counts however long the road is.
        base = re.sub(r"\d+(번길|길)$", "", road)
        for d in docs:
            if base and any(t.startswith(base) for t in d.get("road_address_name", "").split()):
                return d
        for d in docs:
            # Without a dong or road to be near, the city itself is the only check left.
            if km((float(d["x"]), float(d["y"])), near) <= MAX_KM_FROM_DONG if anchored else self.city.name in d["address_name"]:
                return d
        return None

    def resolve(self, place: str) -> Geo:
        dong, rest = split_place(place, self.city)
        # '광명로 KR모터스': the leading road anchors the search like a dong would, and is the fallback point.
        tokens = rest.split()
        road = tokens[0] if len(tokens) > 1 and ROAD_ONLY.match(tokens[0]) else ""
        tail = " ".join(tokens[1:]) if road else ""
        center = self._dong_center(dong) if dong else None
        road_center = self._dong_center(road) if road and not dong else None
        anchor = center or road_center
        near = anchor or self.city.center
        bare = JUNCTION.sub("", rest)
        # '1083 소화전', '256-1 교차로모퉁이': a leading lot number is the useful part.
        lot = LEADING_JIBUN.match(bare)
        if lot:
            rest = lot.group(0).strip()

        # A bare lot number means nothing without its dong.
        if rest and ((dong and JIBUN.match(rest)) or ROAD_WITH_NUMBER.search(rest) or ROAD_ONLY.match(rest)):
            d = self._address(f"{dong} {rest}" if JIBUN.match(rest) else rest)
            # Legal dongs can be wide (Anyang's 호계동 spans three administrative dongs), so a lot found
            # under the same city and dong counts however far it is from the dong's centre.
            named = dong and self.city.name in d["address_name"] and dong in d["address_name"].split() if d else False
            if d and (anchor is None or named or km((float(d["x"]), float(d["y"])), anchor) <= MAX_KM_FROM_DONG):
                precision = "road" if ROAD_ONLY.match(rest) else "address"
                return Geo(place, float(d["x"]), float(d["y"]), precision, d["address_name"])
        # A bare road name never names a shop, nor does an address the lookup could not find
        # ('갈현동 25' would match 'GS25'); keyword search would return unrelated hits.
        if rest and not (ROAD_ONLY.match(rest) or JIBUN.match(rest) or ROAD_WITH_NUMBER.search(rest)):
            for q in dict.fromkeys([f"{dong} {rest}".strip(), rest, tail, bare]):
                # '평동사거리' minus the junction is just the dong name; nothing left to search.
                if not q.strip() or q.strip() == dong:
                    continue
                d = self._landmark(q, dong, near, anchor is not None, road if not dong else "")
                if d:
                    return Geo(place, float(d["x"]), float(d["y"]), "landmark", d["place_name"])
        if center:
            return Geo(place, center[0], center[1], "dong", dong)
        if road_center:
            return Geo(place, road_center[0], road_center[1], "road", road)
        return Geo(place, None, None, "none")

    def geocode(self, places: list[str], progress=None) -> dict[str, Geo]:
        with self.cache_path.open("a", encoding="utf-8") as f:
            for n, p in enumerate(places, 1):
                if p not in self.cache:
                    g = self.resolve(p)
                    self.cache[p] = g
                    f.write(json.dumps(asdict(g), ensure_ascii=False) + "\n")
                if progress:
                    progress(n, len(places))
        return {p: self.cache[p] for p in places}
