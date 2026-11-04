# Checks whether an old weekday × hour enforcement pattern still holds in a later period
from __future__ import annotations

from collections import defaultdict
from datetime import date

from .aggregate import weekday_totals
from .records import Enforcement

Rates = dict[tuple[str, int, int], float]


def street_key(place: str) -> str:
    """'고색동 산업로' and '산업로 85' both become '산업로'; '고색동 982 횡단보도' becomes '982'.

    The zone dataset dropped the dong prefix and added building numbers from 2024 on,
    so periods are only comparable at street or lot level.
    """
    tokens = place.split()
    while len(tokens) > 1 and tokens[0].endswith("동"):
        tokens.pop(0)
    return tokens[0]


def day_rates(records: list[Enforcement], first: date, last: date) -> Rates:
    """Share of each weekday within [first, last] that had enforcement at that street and hour."""
    days: dict[tuple[str, int, int], set[date]] = defaultdict(set)
    for r in records:
        d = r.at.date()
        if first <= d <= last:
            days[(street_key(r.place), d.weekday(), r.at.hour)].add(d)
    totals = weekday_totals(first, last)
    return {k: len(v) / totals[k[1]] for k, v in days.items()}


def compare(old: Rates, new: Rates, k: int) -> dict[str, float]:
    """corr: Pearson over cells seen in either period (missing = 0).
    top_overlap: share of the old top-k cells that are also in the new top-k.
    lift: mean new rate of the old top-k cells over the mean new rate of all cells.
    """
    cells = sorted(old.keys() | new.keys())
    xs = [old.get(c, 0.0) for c in cells]
    ys = [new.get(c, 0.0) for c in cells]
    n = len(cells)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    top_old = sorted(old, key=lambda c: old[c], reverse=True)[:k]
    top_new = set(sorted(new, key=lambda c: new[c], reverse=True)[:k])
    return {
        "cells": n,
        "corr": cov / var if var else 0.0,
        "top_overlap": len(top_new.intersection(top_old)) / len(top_old),
        "lift": (sum(new.get(c, 0.0) for c in top_old) / len(top_old)) / my if my else 0.0,
    }
