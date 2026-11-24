#!/usr/bin/env python3

"""Generates A3A4 key candidates to standard output."""

import argparse
import itertools
import string
import sys

BASE_KEYS = ["4BKNwi77", "yOTmK50z", "OmniW4GX", "Vgz7", "12345678", "123456", "00000000"]
PREFIXES = ["Omni", "omni", "Segway", "NB", "ZK"]

CHARSET = string.ascii_letters + string.digits


def emit_seen(out, seen, k):
    k = k[:8]
    if k and k not in seen:
        seen.add(k)
        out.append(k)


def mutations():
    out, seen = [], set()

    def add(k):
        emit_seen(out, seen, k)

    for k in BASE_KEYS:
        add(k)

    for k in BASE_KEYS:
        for v in (k.lower(), k.upper(), k.capitalize()):
            add(v)

    for p in PREFIXES:
        for k in BASE_KEYS:
            add(p + k)
            add(k + p)

    return out, seen


def digit_suffixes(out, seen, lo, hi, width):

    pad = f"{{:0{width}d}}"
    for k in BASE_KEYS:
        for n in range(lo, hi + 1):
            s = pad.format(n)
            emit_seen(out, seen, k + s)
            emit_seen(out, seen, s + k)


def exhaustive(out, seen, length):
    for tup in itertools.product(CHARSET, repeat=length):
        emit_seen(out, seen, "".join(tup))


def parse_range(s):
    a, _, b = s.partition("-")
    return int(a or 0), int(b or a or 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--digits-suffix",
        default="0-99",
        metavar="A-B",
        help="try base+digits A..B (default 0-99, two digits)",
    )
    ap.add_argument(
        "--exhaust",
        type=int,
        default=0,
        metavar="N",
        help="exhaustive search over [A-Za-z0-9] with exactly N characters "
        "(WARNING: N=4 ~ 15 million lines)",
    )
    args = ap.parse_args()

    out, seen = mutations()
    n_mut = len(out)

    lo, hi = parse_range(args.digits_suffix)
    width = max(len(str(lo)), len(str(hi)), 2)
    digit_suffixes(out, seen, lo, hi, width)
    n_suf = len(out) - n_mut

    if args.exhaust:
        tot = len(CHARSET) ** args.exhaust
        print(f"exhaustive search N={args.exhaust}: {tot:,} candidates", file=sys.stderr)
        exhaustive(out, seen, args.exhaust)

    for k in out:
        print(k)

    print(
        f"done: {len(out):,} candidates " f"(mutations {n_mut:,}, suffixes {n_suf:,})",
        file=sys.stderr,
    )
    if not args.exhaust:
        s = max(1.0, len(out) / 4 / 3600)
        print(f"estimated sweep time at 4 attempts/s: ~{s:.1f} h", file=sys.stderr)


if __name__ == "__main__":
    main()
