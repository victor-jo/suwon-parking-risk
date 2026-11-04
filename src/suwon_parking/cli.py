# Command-line entry point: fetch raw data / print a quick profile
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .fetch import SOURCES, download
from .geocode import SEONGNAM, SUWON, City
from .records import hourly_counts, parse_enforcements, parse_reports, place_coverage

RAW = Path("data/raw")
# 100 m caught a report near most points (68%); 50 m keeps the badge meaningful.
RECENT_KM = 0.05
GEOCODE_TOP = 3000


@dataclass(frozen=True, slots=True)
class Region:
    city: City
    source: str  # key in SOURCES
    cache: Path  # one cache per city: the same place text can name different spots in two cities
    year: int | None = None  # keep only this year's records


REGIONS = {
    "suwon": Region(SUWON, "enforcement", Path("data/geocode_cache.jsonl")),
    # 2024 only has records from mid-November; a full calendar year keeps the day share honest.
    "seongnam": Region(SEONGNAM, "seongnam", Path("data/geocode_cache_seongnam.jsonl"), year=2025),
}


def load_records(region: Region):
    records = parse_enforcements((RAW / SOURCES[region.source].filename).read_bytes())
    return [r for r in records if region.year is None or r.at.year == region.year]


def cmd_fetch(args: argparse.Namespace) -> None:
    for name in args.names or SOURCES:
        print(f"{name} → {download(SOURCES[name], RAW)}")


def cmd_profile(args: argparse.Namespace) -> None:
    records = parse_enforcements((RAW / SOURCES["enforcement"].filename).read_bytes())
    print(f"records {len(records)}, {min(r.at for r in records)} ~ {max(r.at for r in records)}")
    print(f"unique places {len({r.place for r in records})}")
    for n in (100, 1000, 3000):
        print(f"  top {n} places cover {place_coverage(records, n):.1%}")
    print("methods", Counter(r.method for r in records).most_common())
    print("by hour", hourly_counts(records))


def cmd_geocode(args: argparse.Namespace) -> None:
    from .geocode import KakaoGeocoder

    region = REGIONS[args.city]
    if args.fines:
        records = parse_reports((RAW / SOURCES["fines"].filename).read_bytes())
    else:
        records = load_records(region)
    counts = Counter(r.place for r in records)
    places = [p for p, _ in counts.most_common(args.top)]
    geo = KakaoGeocoder.from_env(region.cache, region.city)

    def progress(done: int, total: int) -> None:
        if done % 250 == 0 or done == total:
            print(f"  {done}/{total}", flush=True)

    result = geo.geocode(places, progress=progress)
    by_precision = Counter()
    for p, g in result.items():
        by_precision[g.precision] += counts[p]
    total = len(records)
    print(f"top {len(places)} places = {sum(by_precision.values()) / total:.1%} of records")
    for k, v in by_precision.most_common():
        print(f"  {k:9} {v / total:.1%}")


def load_cache(region: Region = REGIONS["suwon"]) -> dict:
    from .geocode import KakaoGeocoder

    return dict(KakaoGeocoder("", region.cache).cache)  # cache only, no API calls


def load_geo(records, region: Region = REGIONS["suwon"]) -> dict:
    """Kakao cache for the top GEOCODE_TOP places, overridden by camera coordinates where a place names a camera.

    The cache also holds places geocoded for other datasets; letting them in would add map points
    only because those places show up elsewhere (e.g. in the 2025 reports).
    """
    from .cctv import match_places, parse_cameras

    top = {p for p, _ in Counter(r.place for r in records).most_common(GEOCODE_TOP)}
    geo = {p: g for p, g in load_cache(region).items() if p in top}
    if region.city != SUWON:  # only Suwon's camera list names spots the way place texts do
        return geo
    cameras = parse_cameras((RAW / SOURCES["cctv"].filename).read_bytes())
    geo.update(match_places(sorted({r.place for r in records}), cameras))
    return geo


def cmd_validate(args: argparse.Namespace) -> None:
    from .cctv import match_places, parse_cameras
    from .geocode import KakaoGeocoder, km

    records = parse_enforcements((RAW / SOURCES["enforcement"].filename).read_bytes())
    kakao = KakaoGeocoder("", Path("data/geocode_cache.jsonl")).cache
    truth = match_places(sorted({r.place for r in records}), parse_cameras((RAW / SOURCES["cctv"].filename).read_bytes()))
    fixed = Counter(r.place for r in records if r.method == "고정형")
    print(f"camera-named places {len(truth)}, cover {sum(fixed[p] for p in truth) / sum(fixed.values()):.1%} of fixed-camera records")
    errors: dict[str, list[tuple[float, str, str]]] = {}
    for p, t in truth.items():
        g = kakao.get(p)
        if g and g.lon is not None:
            errors.setdefault(g.precision, []).append((km((g.lon, g.lat), (t.lon, t.lat)), p, g.matched))
    for prec, errs in sorted(errors.items(), key=lambda e: -len(e[1])):
        d = sorted(e[0] for e in errs)
        print(f"  {prec:9} n={len(d):4}  median {d[len(d) // 2] * 1000:5.0f}m  p90 {d[int(0.9 * (len(d) - 1))] * 1000:5.0f}m"
              f"  within 200m {sum(x < 0.2 for x in d) / len(d):4.0%}")
    worst = sorted(errors.get("landmark", []), reverse=True)[: args.worst]
    for dist, p, m in worst:
        print(f"    {dist:5.2f}km  {p[:28]} → {m[:28]}")


def cmd_aggregate(args: argparse.Namespace) -> None:
    from .aggregate import aggregate, write_cells

    records = parse_enforcements((RAW / SOURCES["enforcement"].filename).read_bytes())
    geo = load_geo(records)
    cells = aggregate(records, geo)
    out = Path("data/cells.csv")
    write_cells(cells, out)
    print(f"{len(cells)} cells, {len({(c.lon, c.lat) for c in cells})} points → {out}")
    days = "월화수목금토일"
    for c in cells[: args.show]:
        print(f"  {c.day_rate:5.0%}  {days[c.weekday]} {c.hour:02d}시  [{c.precision}/{c.method}] {c.places[:40]}")


def cmd_freshness(args: argparse.Namespace) -> None:
    from datetime import date

    from .freshness import compare, day_rates

    records = parse_enforcements((RAW / SOURCES["zones"].filename).read_bytes())
    periods = {"2021": (date(2021, 1, 1), date(2021, 12, 31)),
               "2022-01~2023-10": (date(2022, 1, 1), date(2023, 10, 31)),
               "2024-2025": (date(2024, 1, 1), date(2025, 12, 31))}
    rates = {name: day_rates(records, *span) for name, span in periods.items()}
    base = "2022-01~2023-10"  # same span as the main enforcement dataset
    for name in ("2021", "2024-2025"):
        s = compare(rates[base], rates[name], args.top)
        print(f"{base} → {name}: cells {s['cells']}, corr {s['corr']:.2f}, "
              f"top {args.top} overlap {s['top_overlap']:.0%}, lift {s['lift']:.1f}x")
    days = "월화수목금토일"
    old, new = rates[base], rates["2024-2025"]
    print(f"old top {args.top} cells: old rate → 2024-2025 rate")
    for c in sorted(old, key=lambda c: old[c], reverse=True)[: args.top]:
        print(f"  {c[0]:10} {days[c[1]]} {c[2]:02d}시  {old[c]:4.0%} → {new.get(c, 0.0):4.0%}")


def load_points():
    """Map points from the main records, with nearby 2025-09 citizen reports attached."""
    from .points import attach_recent, summarize

    records = parse_enforcements((RAW / SOURCES["enforcement"].filename).read_bytes())
    points = summarize(records, load_geo(records))
    attach_recent(points, parse_reports((RAW / SOURCES["fines"].filename).read_bytes()), load_cache(), RECENT_KM)
    return records, points


def cmd_recent(args: argparse.Namespace) -> None:
    from dataclasses import replace

    from .aggregate import EXACT
    from .points import attach_recent

    _, points = load_points()
    reports = parse_reports((RAW / SOURCES["fines"].filename).read_bytes())
    geo = load_cache()
    rate = lambda ps: sum(p.recent > 0 for p in ps) / len(ps)
    print(f"exactly located points with a fined citizen report within {RECENT_KM * 1000:.0f} m in 2025-09")
    for kind in ("patrol", "cctv"):
        pts = sorted((p for p in points if p.kind == kind and p.precision in EXACT), key=lambda p: -p.day_share)
        top = pts[: max(1, len(pts) // 10)]
        # Control: the same points moved 500 m north, i.e. similar neighbourhoods but not the enforced spot.
        moved = [replace(p, lat=p.lat + 0.0045, recent=0) for p in pts]
        attach_recent(moved, reports, geo, RECENT_KM)
        print(f"  {kind:6} all {len(pts):4}: {rate(pts):4.0%}   old top 10%: {rate(top):4.0%}"
              f"   moved 500 m north: {rate(moved):4.0%}")


def cmd_map(args: argparse.Namespace) -> None:
    from collections import Counter as C

    from .mapview import render

    records, points = load_points()
    period = f"{min(r.at for r in records):%Y-%m-%d} ~ {max(r.at for r in records):%Y-%m-%d}"
    out = Path("data/map.html")
    out.write_text(render(points, period, len(records)), encoding="utf-8")
    print(f"{len(points)} points {dict(C(p.kind for p in points))}, {sum(p.recent > 0 for p in points)} with 2025-09 reports,"
          f" {out.stat().st_size / 1e6:.1f} MB → {out}")


def main() -> None:
    p = argparse.ArgumentParser(prog="suwon-parking")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download raw datasets from data.go.kr")
    f.add_argument("names", nargs="*", help=f"subset of {', '.join(SOURCES)} (default: all)")
    f.set_defaults(func=cmd_fetch)
    sub.add_parser("profile", help="print counts, coverage and hourly pattern").set_defaults(func=cmd_profile)
    g = sub.add_parser("geocode", help="resolve the most frequent place texts to coordinates (Kakao)")
    g.add_argument("--top", type=int, default=GEOCODE_TOP)
    g.add_argument("--city", choices=REGIONS, default="suwon")
    g.add_argument("--fines", action="store_true", help="geocode the 2025-09 citizen-report places instead (Suwon)")
    g.set_defaults(func=cmd_geocode)
    v = sub.add_parser("validate", help="score Kakao geocodes against fixed-camera coordinates")
    v.add_argument("--worst", type=int, default=8)
    v.set_defaults(func=cmd_validate)
    a = sub.add_parser("aggregate", help="point × weekday × hour counts from the geocode cache")
    a.add_argument("--show", type=int, default=15)
    a.set_defaults(func=cmd_aggregate)
    fr = sub.add_parser("freshness", help="does the zone's 2022-23 pattern still hold in 2021 and 2024-25?")
    fr.add_argument("--top", type=int, default=10)
    fr.set_defaults(func=cmd_freshness)
    sub.add_parser("recent", help="are old hot spots still reported in 2025-09? (city-wide)").set_defaults(func=cmd_recent)
    sub.add_parser("map", help="write a self-contained map page to data/map.html").set_defaults(func=cmd_map)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
