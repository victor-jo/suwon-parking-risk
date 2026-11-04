# Summarizes enforcement per map point: how often it happens, by what means, and a weekday × hour grid
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from .aggregate import EXACT, assign_points, weekday_totals
from .geocode import SUWON_CENTER, Geo, km
from .records import Enforcement, Report


@dataclass(slots=True)
class Point:
    lon: float
    lat: float
    precision: str
    label: str
    places: str  # up to three most frequent place texts
    kind: str  # "cctv" when fixed cameras made most of the records, otherwise "patrol"
    count: int
    day_share: float  # share of all days in the period with at least one enforcement here
    grid: list[int]  # weekday * 24 + hour → day rate in percent (reference only)
    recent: int = 0  # days in the recent report month with a fined report nearby


def summarize(records: list[Enforcement], geo: dict[str, Geo], hours: bool = True) -> list[Point]:
    """Per-point summary; with hours=False (records carry dates only) the grid stays empty."""
    point_of, info = assign_points(geo)
    dates: dict[tuple, set[date]] = defaultdict(set)
    cell_dates: dict[tuple, set[date]] = defaultdict(set)
    places: dict[tuple, Counter] = defaultdict(Counter)
    methods: dict[tuple, Counter] = defaultdict(Counter)
    for r in records:
        pt = point_of.get(r.place)
        if pt is None:
            continue
        d = r.at.date()
        dates[pt].add(d)
        if hours:
            cell_dates[(pt, d.weekday() * 24 + r.at.hour)].add(d)
        places[pt][r.place] += 1
        methods[pt][r.method] += 1

    first = min(r.at.date() for r in records)
    last = max(r.at.date() for r in records)
    total_days = (last - first).days + 1
    per_weekday = weekday_totals(first, last)
    grids: dict[tuple, list[int]] = defaultdict(lambda: [0] * 168)
    for (pt, slot), ds in cell_dates.items():
        grids[pt][slot] = round(100 * len(ds) / per_weekday[slot // 24])

    out = []
    for pt, ds in dates.items():
        lon, lat, precision, matched = info[pt]
        m = methods[pt]
        out.append(Point(
            lon, lat, precision,
            # Camera and landmark names read well; Kakao address names are long and dong names vague.
            label=matched if matched and precision in ("cctv", "landmark") else places[pt].most_common(1)[0][0],
            places=" | ".join(p for p, _ in places[pt].most_common(3)),
            # Suwon labels fixed cameras '고정형', Seongnam '고정형CCTV'.
            kind="cctv" if sum(n for k, n in m.items() if k.startswith("고정형")) * 2 > m.total() else "patrol",
            count=m.total(),
            day_share=len(ds) / total_days,
            grid=grids[pt],
        ))
    out.sort(key=lambda p: p.day_share, reverse=True)
    return out


def attach_recent(points: list[Point], reports: list[Report], geo: dict[str, Geo], radius_km: float = 0.1) -> None:
    """Set each exactly located point's `recent` to the number of days with a report within radius_km.

    Only exact locations on both sides: a dong centre near a report says nothing about either.
    """
    days_at: dict[tuple[float, float], set] = defaultdict(set)
    for r in reports:
        g = geo.get(r.place)
        if g and g.lon is not None and g.precision in EXACT:
            days_at[(g.lon, g.lat)].add(r.day)
    # Bucket report spots on a grid at least radius_km wide so each point checks only its 3 x 3 neighbourhood.
    # A degree of longitude shrinks with latitude, so its step is widened to stay >= radius_km.
    lat_step = radius_km / 111.0
    lon_step = lat_step / math.cos(math.radians(SUWON_CENTER[1] + 0.5))
    buckets: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for spot in days_at:
        buckets[(int(spot[0] // lon_step), int(spot[1] // lat_step))].append(spot)
    for p in points:
        if p.precision not in EXACT:
            continue
        bx, by = int(p.lon // lon_step), int(p.lat // lat_step)
        days: set = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for spot in buckets.get((bx + dx, by + dy), ()):
                    if km((p.lon, p.lat), spot) <= radius_km:
                        days |= days_at[spot]
        p.recent = len(days)
