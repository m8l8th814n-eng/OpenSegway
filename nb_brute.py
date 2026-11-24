#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nb_brute.py - genererar nyckelkandidater (A3A4 deviceKey) till stdout.

Bara generatorn - sjalva provningen gor nb_sweep.py, sa att vi kan granska
listan forst:

  python3 nb_brute.py > kandidater.txt          # mutationer av kanda nycklar
  sudo python3 nb_sweep.py --wordlist kandidater.txt

  python3 nb_brute.py --exhaust 4               # ren uttomning, max 4 tecken
  python3 nb_brute.py --digits-suffix 0-999     # bredare siffersuffix

Regler:
- protokollet nollstoppar vid 8 byte -> kandidater kortas till 8, dubbletter
  tas bort, ordningen ar stabil (kanda nycklar forst).
- statistik gar till stderr sa stdout ar ren att pipa.
"""
import argparse
import itertools
import string
import sys

# kanda nycklar (STATUS.md 8) + langshots
BAS = ["4BKNwi77", "yOTmK50z", "OmniW4GX", "Vgz7",
       "12345678", "123456", "00000000"]
ORD = ["Omni", "omni", "Segway", "NB", "ZK"]   # troliga prefix att kombinera

CHARSET = string.ascii_letters + string.digits   # [A-Za-z0-9]


def emit_seen(out, seen, k):
    k = k[:8]
    if k and k not in seen:
        seen.add(k)
        out.append(k)


def mutations():
    out, seen = [], set()

    def add(k):
        emit_seen(out, seen, k)

    for k in BAS:
        add(k)  # kanda forst, exakt som de ar

    # case-varianter av basen
    for k in BAS:
        for v in (k.lower(), k.upper(), k.capitalize()):
            add(v)

    # prefix-kombinationer: ORD + bas och bas + ORD
    for p in ORD:
        for k in BAS:
            add(p + k)
            add(k + p)

    return out, seen


def digit_suffixes(out, seen, lo, hi, width):
    """bas + siffror: 4BKNwi77.. med suffix 0..hi."""
    pad = f"{{:0{width}d}}"
    for k in BAS:
        for n in range(lo, hi + 1):
            s = pad.format(n)
            if len(s) > width:      # n fyllde ut bredden
                pass
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
    ap.add_argument("--digits-suffix", default="0-99", metavar="A-B",
                    help="prova bas+siffror A..B (default 0-99, tvasiffrigt)")
    ap.add_argument("--exhaust", type=int, default=0, metavar="N",
                    help="ren uttomning over [A-Za-z0-9] med exakt N tecken "
                         "(VARNING: N=4 ~ 15 miljoner rader)")
    args = ap.parse_args()

    out, seen = mutations()
    n_mut = len(out)

    lo, hi = parse_range(args.digits_suffix)
    width = max(len(str(lo)), len(str(hi)), 2)
    digit_suffixes(out, seen, lo, hi, width)
    n_suf = len(out) - n_mut

    if args.exhaust:
        tot = len(CHARSET) ** args.exhaust
        print(f"uttomning N={args.exhaust}: {tot:,} kandidater",
              file=sys.stderr)
        exhaustive(out, seen, args.exhaust)

    for k in out:
        print(k)

    print(f"klart: {len(out):,} kandidater "
          f"(mutationer {n_mut:,}, suffix {n_suf:,})",
          file=sys.stderr)
    if not args.exhaust:
        s = max(1.0, len(out) / 4 / 3600)
        print(f"uppskattad sveptid vid 4 forsok/s: ~{s:.1f} h",
              file=sys.stderr)


if __name__ == "__main__":
    main()
