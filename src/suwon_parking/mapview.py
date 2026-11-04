# Renders map points into a single self-contained HTML page (data inlined, no server needed)
from __future__ import annotations

import json
from pathlib import Path

from .points import Point

TEMPLATE = Path(__file__).with_name("map_template.html")


def render(points: list[Point], period: str, records: int) -> str:
    rows = [
        [p.lon, p.lat, p.precision, p.label, p.places, p.kind, p.count, round(p.day_share, 4),
         [[slot, pct] for slot, pct in enumerate(p.grid) if pct], p.recent]
        for p in points
    ]
    data = json.dumps({"period": period, "records": records, "points": rows}, ensure_ascii=False, separators=(",", ":"))
    # A place text containing '</script>' must not end the inline script early.
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", data.replace("</", "<\\/"))
