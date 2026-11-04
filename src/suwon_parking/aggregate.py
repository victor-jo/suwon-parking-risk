# Aggregates geocoded enforcement records into point × weekday × hour counts and day rates
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .geocode import Geo
from .records import Enforcement

EXACT = {"address", "landmark"}


@dataclass(slots=True)
class Cell:
    lon: float
    lat: float
    precision: str
    label: str
    places: str
    method: str  # most frequent enforcement method in this cell
    weekday: int  # Monday = 0
    hour: int
    count: int
    days: int  # distinct dates with at least one enforcement in this cell
    day_rate: float  # days / number of such weekdays in the period


def weekday_totals(first: date, last: date) -> list[int]:
    totals = [0] * 7
    d = first
    while d <= last:
        totals[d.weekday()] += 1
        d += timedelta(days=1)
    return totals


def aggregate(records: list[Enforcement], geo: dict[str, Geo]) -> list[Cell]:
    """Merge places that resolve to the same exact point, then count per weekday and hour.

    Places that only resolved to a road or dong centre stay separate: merging every
    vague place in a dong onto its centre would inflate that point's rate.
    """
    point_of: dict[str, tuple] = {}
    info: dict[tuple, tuple[float, float, str, str]] = {}
    for place, g in geo.items():
        if g.lon is None or g.lat is None:
            continue
        lon, lat = round(g.lon, 5), round(g.lat, 5)
        pt = (lon, lat) if g.precision in EXACT else (lon, lat, place)
        point_of[place] = pt
        info.setdefault(pt, (lon, lat, g.precision, g.matched))

    counts: Counter = Counter()
    dates: dict[tuple, set[date]] = defaultdict(set)
    place_hits: dict[tuple, Counter] = defaultdict(Counter)
    methods: dict[tuple, Counter] = defaultdict(Counter)
    for r in records:
        pt = point_of.get(r.place)
        if pt is None:
            continue
        key = (pt, r.at.weekday(), r.at.hour)
        counts[key] += 1
        dates[key].add(r.at.date())
        place_hits[pt][r.place] += 1
        methods[key][r.method] += 1

    first = min(r.at.date() for r in records)
    last = max(r.at.date() for r in records)
    totals = weekday_totals(first, last)
    cells = []
    for (pt, wd, hr), n in counts.items():
        lon, lat, precision, label = info[pt]
        top_places = " | ".join(p for p, _ in place_hits[pt].most_common(3))
        method = methods[(pt, wd, hr)].most_common(1)[0][0]
        days = len(dates[(pt, wd, hr)])
        cells.append(Cell(lon, lat, precision, label, top_places, method, wd, hr, n, days, days / totals[wd]))
    cells.sort(key=lambda c: c.day_rate, reverse=True)
    return cells


def write_cells(cells: list[Cell], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(Cell.__slots__)
        for c in cells:
            w.writerow([getattr(c, k) if k != "day_rate" else f"{c.day_rate:.4f}" for k in Cell.__slots__])
