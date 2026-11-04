# Parses the cp949 enforcement CSV into typed records and aggregates place/time counts
from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Enforcement:
    at: datetime
    office: str
    place: str
    method: str


def parse_enforcements(raw: bytes) -> list[Enforcement]:
    reader = csv.DictReader(io.StringIO(raw.decode("cp949")))
    out = []
    for row in reader:
        place = row["단속장소"].strip()
        if not place:
            continue
        out.append(
            Enforcement(
                at=datetime.fromisoformat(row["단속일시정보"]),
                office=row["관리기관명"],
                place=place,
                method=row["단속방법"],
            )
        )
    return out


def place_coverage(records: list[Enforcement], top_n: int) -> float:
    """Share of records whose place text is among the top_n most frequent places."""
    counts = Counter(r.place for r in records)
    return sum(c for _, c in counts.most_common(top_n)) / len(records)


def hourly_counts(records: list[Enforcement]) -> list[int]:
    hours = [0] * 24
    for r in records:
        hours[r.at.hour] += 1
    return hours
