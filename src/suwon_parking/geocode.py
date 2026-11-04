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
SUWON_CENTER = (127.0286, 37.2636)  # lon, lat
MAX_KM_FROM_DONG = 1.5

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


@dataclass(frozen=True, slots=True)
class Geo:
    place: str
    lon: float | None
    lat: float | None
    precision: str  # address | landmark | road | dong | none
    matched: str = ""


def split_place(place: str) -> tuple[str, str]:
    """Split '인계동 인계동 교동짬뽕 앞 (메모)' into ('인계동', '교동짬뽕')."""
    text = re.sub(r"\(.*?\)", " ", place)
    # Full addresses ('경기도수원시권선구평동 수원시 권선구 평동 38') keep only what follows the last city/gu.
    # Only the city as an address part: '수원시청역' or '수원시립미술관' must survive.
    text = re.split(r"수원시(?=\s|(?:장안|권선|팔달|영통)구)", text)[-1]
    text = re.sub(r"^\s*(장안|권선|팔달|영통)구\s+", "", text)
    tokens = text.split()
    if not tokens:
        return "", ""
    dong = tokens[0]
    rest = [t for t in tokens[1:] if t != dong]
    rest = " ".join(rest)
    rest = RELATIVE.sub(" ", rest)
    return dong, re.sub(r"\s+", " ", rest).strip()


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = (a[0] - b[0]) * 111.0 * math.cos(math.radians(a[1]))
    dy = (a[1] - b[1]) * 111.0
    return math.hypot(dx, dy)


class KakaoGeocoder:
    def __init__(self, key: str, cache_path: Path, client: httpx.Client | None = None):
        self.client = client or httpx.Client(headers={"Authorization": f"KakaoAK {key}"}, timeout=10)
        self.cache_path = cache_path
        self.cache: dict[str, Geo] = {}
        self.dongs: dict[str, tuple[float, float] | None] = {}
        if cache_path.exists():
            for line in cache_path.open(encoding="utf-8"):
                g = Geo(**json.loads(line))
                self.cache[g.place] = g

    @classmethod
    def from_env(cls, cache_path: Path, env_file: Path = Path(".env")) -> KakaoGeocoder:
        key = os.environ.get("KAKAO_REST_API_KEY")
        if not key and env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("KAKAO_REST_API_KEY="):
                    key = line.split("=", 1)[1].strip()
        if not key:
            raise RuntimeError("KAKAO_REST_API_KEY is not set (env or .env)")
        return cls(key, cache_path)

    def _get(self, kind: str, **params) -> list[dict]:
        resp = self.client.get(f"{KAKAO}/{kind}.json", params=params)
        resp.raise_for_status()
        return resp.json()["documents"]

    def _address(self, query: str) -> dict | None:
        docs = self._get("address", query=f"수원시 {query}")
        return docs[0] if docs else None

    def _dong_center(self, dong: str) -> tuple[float, float] | None:
        if dong not in self.dongs:
            d = self._address(dong)
            self.dongs[dong] = (float(d["x"]), float(d["y"])) if d else None
        return self.dongs[dong]

    def _landmark(self, query: str, dong: str, near: tuple[float, float]) -> dict | None:
        docs = self._get(
            "keyword", query=f"수원 {query}", x=near[0], y=near[1], radius=20000, size=15, sort="accuracy"
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
        for d in docs:
            if km((float(d["x"]), float(d["y"])), near) <= MAX_KM_FROM_DONG:
                return d
        return None

    def resolve(self, place: str) -> Geo:
        dong, rest = split_place(place)
        center = self._dong_center(dong) if dong else None
        near = center or SUWON_CENTER
        bare = JUNCTION.sub("", rest)
        # '1083 소화전', '256-1 교차로모퉁이': a leading lot number is the useful part.
        lot = LEADING_JIBUN.match(bare)
        if lot:
            rest = lot.group(0).strip()

        if rest and (JIBUN.match(rest) or ROAD_WITH_NUMBER.search(rest) or ROAD_ONLY.match(rest)):
            d = self._address(f"{dong} {rest}" if JIBUN.match(rest) else rest)
            if d and (center is None or km((float(d["x"]), float(d["y"])), center) <= MAX_KM_FROM_DONG):
                precision = "road" if ROAD_ONLY.match(rest) else "address"
                return Geo(place, float(d["x"]), float(d["y"]), precision, d["address_name"])
        # A bare road name never names a shop; keyword search would return unrelated hits.
        if rest and not ROAD_ONLY.match(rest):
            for q in dict.fromkeys([f"{dong} {rest}", rest, bare]):
                # '평동사거리' minus the junction is just the dong name; nothing left to search.
                if not q.strip() or q.strip() == dong:
                    continue
                d = self._landmark(q, dong, near)
                if d:
                    return Geo(place, float(d["x"]), float(d["y"]), "landmark", d["place_name"])
        if center:
            return Geo(place, center[0], center[1], "dong", dong)
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
