# Renders map points into a single self-contained HTML page (data inlined, no server needed)
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .points import Point

TEMPLATE = Path(__file__).with_name("map_template.html")


@dataclass(frozen=True, slots=True)
class CityLayer:
    name: str
    period: str
    records: int
    points: list[Point]
    hours: bool  # records carry a time of day, so the weekday × hour grid means something
    # Popup lines for a point's `recent` count: (text with '{n}', text when zero); None if the city has no such signal.
    recent: tuple[str, str] | None = None
    reports_only: bool = False  # only citizen reports, no camera or patrol enforcement


def render(cities: list[CityLayer]) -> str:
    rows = [
        [p.lon, p.lat, p.precision, p.label, p.places, p.kind, p.count, round(p.day_share, 4),
         [[slot, pct] for slot, pct in enumerate(p.grid) if pct], p.recent, i]
        for i, c in enumerate(cities)
        for p in c.points
    ]
    meta = [{"name": c.name, "period": c.period, "records": c.records, "hours": c.hours,
             "recent": {"hit": c.recent[0], "miss": c.recent[1]} if c.recent else None,
             "reportsOnly": c.reports_only}
            for c in cities]
    data = json.dumps({"cities": meta, "points": rows}, ensure_ascii=False, separators=(",", ":"))
    # A place text containing '</script>' must not end the inline script early.
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", data.replace("</", "<\\/"))
