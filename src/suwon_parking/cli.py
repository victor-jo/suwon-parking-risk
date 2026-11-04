# Command-line entry point: fetch raw data / print a quick profile
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .fetch import SOURCES, download
from .records import hourly_counts, parse_enforcements, place_coverage

RAW = Path("data/raw")


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

    records = parse_enforcements((RAW / SOURCES["enforcement"].filename).read_bytes())
    counts = Counter(r.place for r in records)
    places = [p for p, _ in counts.most_common(args.top)]
    geo = KakaoGeocoder.from_env(Path("data/geocode_cache.jsonl"))

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


def load_geo(records) -> dict:
    """Kakao cache, overridden by camera coordinates wherever a place names a known camera."""
    from .cctv import match_places, parse_cameras
    from .geocode import KakaoGeocoder

    geo = dict(KakaoGeocoder("", Path("data/geocode_cache.jsonl")).cache)  # cache only, no API calls
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


def main() -> None:
    p = argparse.ArgumentParser(prog="suwon-parking")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download raw datasets from data.go.kr")
    f.add_argument("names", nargs="*", help=f"subset of {', '.join(SOURCES)} (default: all)")
    f.set_defaults(func=cmd_fetch)
    sub.add_parser("profile", help="print counts, coverage and hourly pattern").set_defaults(func=cmd_profile)
    g = sub.add_parser("geocode", help="resolve the most frequent place texts to coordinates (Kakao)")
    g.add_argument("--top", type=int, default=3000)
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
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
