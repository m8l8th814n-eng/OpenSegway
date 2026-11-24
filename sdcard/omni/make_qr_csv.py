#!/usr/bin/env python3
"""Generates omni_qr.csv with IMEI, QR code, and MAC address."""

import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qr", help="QR code/ID (lookup key)")
    ap.add_argument("--mac", help="MAC address, e.g. AA:BB:CC:DD:EE:FF")
    ap.add_argument("--imei", default="0", help="IMEI (may be 0)")
    a = ap.parse_args()

    if a.qr and a.mac:
        print(f"{a.imei},{a.qr},{a.mac}")
        return 0

    rows = [
        ("SC1", "AA:BB:CC:00:00:01"),
        ("SEG1", "AA:BB:CC:00:00:02"),
    ]
    for i, (qr, mac) in enumerate(rows, start=1):
        print(f"86000000000000{i},{qr},{mac}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
