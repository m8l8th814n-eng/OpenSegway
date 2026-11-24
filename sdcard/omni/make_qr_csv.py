#!/usr/bin/env python3
"""Generera omni_qr.csv at appen.

Formatet ar framtaget ur OssUtils.parseQrFile() i den patchade APK:n:
  - en rad per enhet
  - komma-separerat, tre kolumner
  - rader utan komma hoppas over (kan anvandas som kommentar)
  - kolumn 0 (imei)   : sparas men anvands inte for uppslag
  - kolumn 1 (qrcode) : UPPSLAGSNYCKELN - det du skriver i QR-faltet i appen
  - kolumn 2 (mac)    : MAC-adressen appen ansluter till

Kor:  python3 make_qr_csv.py > omni_qr.csv
eller: python3 make_qr_csv.py --mac AA:BB:CC:DD:EE:FF --qr SC1
"""
import argparse
import sys

HEADER = "# imei,qrcode,mac  <- kolumn 2 ar uppslagsnyckeln du skriver i appen"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qr", help="QR-koden/ID (uppslagsnyckeln)")
    ap.add_argument("--mac", help="MAC-adressen, t.ex. AA:BB:CC:DD:EE:FF")
    ap.add_argument("--imei", default="0", help="IMEI (får vara 0)")
    a = ap.parse_args()

    if a.qr and a.mac:
        print(f"{a.imei},{a.qr},{a.mac}")
        return 0

    # exempel: byt till dina enheters riktiga MAC-adresser
    rows = [
        ("SC1", "AA:BB:CC:00:00:01"),
        ("SEG1", "AA:BB:CC:00:00:02"),
    ]
    for i, (qr, mac) in enumerate(rows, start=1):
        print(f"86000000000000{i},{qr},{mac}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
