# Summarizes enforcement per map point: how often it happens, by what means, and a weekday × hour grid
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from .aggregate import assign_points, weekday_totals
from .geocode import Geo
from .records import Enforcement


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


def summarize(records: list[Enforcement], geo: dict[str, Geo]) -> list[Point]:
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
            kind="cctv" if m["고정형"] * 2 > m.total() else "patrol",
            count=m.total(),
            day_share=len(ds) / total_days,
            grid=grids[pt],
        ))
    out.sort(key=lambda p: p.day_share, reverse=True)
    return out
