# Fixed enforcement camera list: matches camera spots to enforcement place texts by name
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from .geocode import Geo


@dataclass(frozen=True, slots=True)
class Camera:
    dong: str
    spot: str
    lon: float
    lat: float


def _norm(s: str) -> str:
    return re.sub(r"[\s()·.,\-]", "", s)


def parse_cameras(raw: bytes) -> list[Camera]:
    reader = csv.DictReader(io.StringIO(raw.decode("cp949")))
    return [Camera(r["단속동"], r["단속지역"], float(r["경도"]), float(r["위도"])) for r in reader]


def match_places(places: list[str], cameras: list[Camera]) -> dict[str, Geo]:
    """Place texts like '원천동 아주대정문삼거리' get the camera's own coordinates."""
    index: dict[str, Camera] = {}
    for c in cameras:
        index.setdefault(_norm(c.dong + c.spot), c)
        index.setdefault(_norm(c.spot), c)
    out = {}
    for p in places:
        tokens = p.split()
        keys = [_norm(p)] + ([_norm(" ".join(tokens[1:]))] if len(tokens) > 1 else [])
        cam = next((index[k] for k in keys if k in index), None)
        if cam:
            out[p] = Geo(p, cam.lon, cam.lat, "cctv", f"{cam.dong} {cam.spot}")
    return out
