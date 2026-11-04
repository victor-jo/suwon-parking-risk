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
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
