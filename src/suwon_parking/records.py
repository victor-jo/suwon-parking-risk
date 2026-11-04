# Parses the enforcement CSVs (Suwon cp949, Seongnam UTF-8) into typed records and aggregates place/time counts
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Enforcement:
    at: datetime
    office: str
    place: str
    method: str


_MANGLED_12H = re.compile(r"(\d{4}-\d\d-\d\d)\s+(\d{1,2}):(\d\d)\S*\s+([AP]M)")


def parse_at(text: str) -> datetime:
    """ISO times, plus unpadded hours ('9:24') and spreadsheet-mangled 12-hour times.

    The mangled form ('2:409:06 PM') keeps hour and minute up front; the rest is noise.
    """
    m = _MANGLED_12H.fullmatch(text.strip())
    if m:
        day, hour, minute, half = m.groups()
        h = int(hour) % 12 + (12 if half == "PM" else 0)
        return datetime.fromisoformat(day).replace(hour=h, minute=int(minute))
    day, _, clock = text.strip().partition(" ")
    if not clock:
        return datetime.fromisoformat(day)
    if clock[1:2] == ":":
        clock = "0" + clock
    return datetime.fromisoformat(f"{day} {clock}")


def _decode(raw: bytes) -> str:
    """Suwon publishes cp949, Seongnam UTF-8 with a byte order mark."""
    return raw.decode("utf-8-sig") if raw.startswith(b"\xef\xbb\xbf") else raw.decode("cp949")


def parse_enforcements(raw: bytes) -> list[Enforcement]:
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    out = []
    for row in reader:
        place = row["단속장소"].strip()
        if not place:
            continue
        out.append(
            Enforcement(
                at=parse_at(row["단속일시정보"]),
                office=row["관리기관명"],
                place=place,
                method=row["단속방법"],
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class Report:
    """A citizen report with a fine; the source only gives the date, not the time."""

    day: date
    office: str
    place: str


def parse_reports(raw: bytes) -> list[Report]:
    reader = csv.DictReader(io.StringIO(raw.decode("cp949")))
    out = []
    for row in reader:
        place = " ".join(row["단속장소"].split())  # some places contain tabs
        if place:
            out.append(Report(date.fromisoformat(row["단속일시정보"].strip()), row["관리기관명"].strip(), place))
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
