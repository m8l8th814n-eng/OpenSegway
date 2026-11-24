#!/usr/bin/env python3

"""Interactive BLE client; requires nb_client.py in the same directory."""

import argparse
import sys
import time

try:
    from nb_client import (
        ORDER_KEY,
        ORDER_OPEN,
        ORDER_CLOSE,
        ORDER_INFO,
        ORDER_SCOOTER_INFO,
        WRITE_UUID,
        NOTIFY_UUID,
        build,
        parse,
        key_payload,
        open_payload,
    )
except ImportError:
    sys.exit("nb_client.py must be in the same directory as nb_client2.py")


def scan(bus, adapter_iface, root, seconds, quiet=False, keep_discovering=False):

    if not quiet:
        print(f"scanning for {int(seconds)} s ...")

    try:
        adapter_iface.SetDiscoveryFilter({"Transport": "le"})
    except Exception as e:
        print(f"    (could not set LE filter: {e})")
    try:
        adapter_iface.StartDiscovery()
    except Exception as e:
        if "InProgress" in str(e) or "Already" in str(e):
            pass
        else:
            print(f"StartDiscovery: {e}")
            return []
    deadline = time.time() + seconds
    seen = {}
    while time.time() < deadline:
        for path, ifaces in root.GetManagedObjects().items():
            if "org.bluez.Device1" not in ifaces:
                continue
            p = ifaces["org.bluez.Device1"]
            addr = str(p.get("Address", ""))
            alias = str(p.get("Alias", ""))
            name = str(p.get("Name", ""))
            rssi = p.get("RSSI", None)
            pair = bool(p.get("Paired", False))
            seen[addr] = {
                "path": str(path),
                "addr": addr,
                "name": name or alias,
                "alias": alias,
                "rssi": int(rssi) if rssi is not None else None,
                "paired": pair,
            }
        pump(0.4)
    if not keep_discovering:
        try:
            adapter_iface.StopDiscovery()
        except Exception:
            pass

    devs = sorted(seen.values(), key=lambda d: (d["name"] == "", -(d["rssi"] or -999)))
    return devs


def show(devs):
    print()
    print(f"{'#':>3}  {'name':32s} {'address':18s} {'rssi':>5}  paired")
    print("-" * 72)
    for i, d in enumerate(devs, 1):
        nm = d["name"][:32] if d["name"] else "(unnamed)"
        rssi = f"{d['rssi']}" if d["rssi"] is not None else "-"
        print(
            f"{i:>3}  {nm:32s} {d['addr']:18s} {rssi:>5}  {'yes' if d['paired'] else '-'}"
        )
    print()


def pump(seconds):

    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    deadline = time.time() + seconds
    while time.time() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def resolve_path(root, address):

    for path, ifaces in root.GetManagedObjects().items():
        if "org.bluez.Device1" not in ifaces:
            continue
        if (
            str(ifaces["org.bluez.Device1"].get("Address", "")).upper()
            == address.upper()
        ):
            return str(path)
    return None


def wait_for_device(adapter_iface, root, address, timeout):

    try:
        adapter_iface.SetDiscoveryFilter({"Transport": "le"})
    except Exception:
        pass
    try:
        adapter_iface.StartDiscovery()
    except Exception:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        p = resolve_path(root, address)
        if p:
            return p
        pump(0.4)
    return None


def fresh_connect(adapter_iface, bus, root, address, name, timeout=15.0):

    p = resolve_path(root, address)
    if p is None:
        p = wait_for_device(adapter_iface, root, address, timeout)
    if p is None:
        print("    device is not currently advertising")
        return None
    try:
        adapter_iface.StopDiscovery()
    except Exception:
        pass
    return connect(adapter_iface, bus, p, name)


def connect(adapter_iface, bus, dev_path, label=""):

    obj = bus.get_object("org.bluez", dev_path)
    dev = dbus_interface(obj, "org.bluez.Device1")
    props = dbus_interface(obj, "org.freedesktop.DBus.Properties")
    for at in ("public", "random"):
        try:
            props.Set("org.bluez.Device1", "AddressType", at)
            break
        except Exception:
            continue
    if label:
        print(f"    connecting {label} ...")
    dev.Connect()
    return dev


def dbus_interface(obj, iface):
    import dbus

    return dbus.Interface(obj, iface)


def find_notify_write(bus, root, timeout=15):
    write_path = notify_path = None
    deadline = time.time() + timeout
    while time.time() < deadline and (write_path is None or notify_path is None):
        for path, ifaces in root.GetManagedObjects().items():
            if "org.bluez.GattCharacteristic1" not in ifaces:
                continue
            u = str(ifaces["org.bluez.GattCharacteristic1"].get("UUID", "")).lower()
            if u == WRITE_UUID:
                write_path = str(path)
            elif u == NOTIFY_UUID:
                notify_path = str(path)
        if write_path is None or notify_path is None:
            time.sleep(0.4)
    return write_path, notify_path


class Session:

    def __init__(self, bus, root, dev, write_path, notify_path):
        import dbus

        self.bus = bus
        self.dev = dev
        self.inbox = []
        self.key = 0x00
        self.write = dbus.Interface(
            bus.get_object("org.bluez", write_path), "org.bluez.GattCharacteristic1"
        )
        self.notify = dbus.Interface(
            bus.get_object("org.bluez", notify_path), "org.bluez.GattCharacteristic1"
        )
        self.notify_path = notify_path

        def on_change(iface, changed, invalidated, path=None):
            if path is not None and str(path) != self.notify_path:
                return
            if "Value" in changed:
                self.inbox.append(bytes(bytearray(changed["Value"])))

        bus.add_signal_receiver(
            on_change,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            path=notify_path,
        )
        self.notify.StartNotify()
        pump(0.5)

    def send(self, order, payload, label, reply_timeout=5.0):
        import dbus

        frame = build(order, payload, self.key)
        print(f"    -> order={order:>3} {label:14s} {frame.hex()}")
        self.write.WriteValue(
            dbus.Array(frame, signature="y"), dbus.Dictionary({}, signature="sv")
        )
        deadline = time.time() + reply_timeout
        while time.time() < deadline:
            while self.inbox:
                value = self.inbox.pop(0)
                o, dec = parse(value)
                if o is None:
                    print(f"       <undecodable reply: {dec}>")
                    continue
                pl = dec[6 : 6 + dec[2]]
                print(
                    f"       <- order={o:>3} status={dec[6]} key=0x{dec[4]:02X} "
                    f"payload={pl.hex()}"
                )
                return o, dec
            pump(0.05)
        print("       (no reply)")
        return None, None

    def handshake(self, device_key):
        print(f"    handshake with deviceKey {device_key!r}")
        _, dec = self.send(ORDER_KEY, key_payload(device_key), "key")
        if dec is None or dec[6] != 1:
            print("    no valid key returned")
            return False
        self.key = dec[7]
        print(f"    OK - session key 0x{self.key:02X}")
        return True

    def close(self):
        try:
            self.notify.StopNotify()
        except Exception:
            pass
        try:
            self.dev.Disconnect()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="Interactive BLE client for fake_lock")
    ap.add_argument("--scan", type=float, default=10.0, help="scan duration in seconds")
    ap.add_argument("--key", default="4BKNwi77", help="deviceKey to send")
    ap.add_argument("--adapter", default="hci0")
    a = ap.parse_args()

    try:
        import dbus
        import dbus.mainloop.glib
    except ImportError:
        sys.exit(
            "missing dbus-python/PyGObject. Packages: python3-dbus python3-gi\n"
            "Run with the system python3."
        )
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_path = f"/org/bluez/{a.adapter}"
    adapter_iface = dbus.Interface(
        bus.get_object("org.bluez", adapter_path), "org.bluez.Adapter1"
    )
    root = dbus.Interface(
        bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager"
    )

    devs = scan(bus, adapter_iface, root, a.scan, keep_discovering=True)
    if not devs:
        print("no devices found")
        return 1

    while True:
        show(devs)
        try:
            val = input("select a number (r = rescan, q = quit): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if val in ("q", ""):
            return 0
        if val == "r":
            devs = scan(bus, adapter_iface, root, a.scan, keep_discovering=True)
            if not devs:
                print("no devices found")
            continue
        if not val.isdigit() or not (1 <= int(val) <= len(devs)):
            print("invalid selection")
            continue

        target = devs[int(val) - 1]
        print(f"\nselected {target['name']!r} ({target['addr']})")
        if target["rssi"] is not None and target["rssi"] < -90:
            print(
                f"    warning: weak signal ({target['rssi']} dBm) - may be difficult to reach"
            )

        sess = None
        try:

            try:
                adapter_iface.StopDiscovery()
            except Exception:
                pass
            dev_path = resolve_path(root, target["addr"])
            if dev_path is None:
                print("    device disappeared from the list - scanning for it again ...")
                dev_path = wait_for_device(adapter_iface, root, target["addr"], 12.0)
            if dev_path is None:
                print("    device no longer found. Choose r to rescan.")
                continue
            try:
                adapter_iface.StopDiscovery()
            except Exception:
                pass
            dev = fresh_connect(
                adapter_iface, bus, root, target["addr"], target["name"]
            )
            write_path, notify_path = find_notify_write(bus, root)
            if not (write_path and notify_path):
                print(
                    "    could not find the service characteristics - is it running fake_lock?"
                )
                continue
            sess = Session(bus, root, dev, write_path, notify_path)
            print("    subscribing to notifications")
            if not sess.handshake(a.key):
                sess.close()
                continue

            sess.send(ORDER_OPEN, open_payload(int(time.time())), "UNLOCK")

            while True:
                try:
                    cmd = (
                        input(
                            "  [u]nlock [l]ock [f] vehicle info [s]tatus "
                            "[a] reconnect [q]uit > "
                        )
                        .strip()
                        .lower()
                    )
                except (EOFError, KeyboardInterrupt):
                    print()
                    return 0
                if cmd == "q" or cmd == "":
                    break
                if cmd == "u":
                    sess.send(ORDER_OPEN, open_payload(int(time.time())), "UNLOCK")
                elif cmd == "l":
                    sess.send(ORDER_CLOSE, open_payload(int(time.time())), "LOCK")
                elif cmd == "f":
                    sess.send(ORDER_SCOOTER_INFO, bytes(8), "vehicle info")
                elif cmd == "s":
                    sess.send(ORDER_INFO, bytes(1), "status")
                elif cmd == "a":
                    devs = scan(bus, adapter_iface, root, a.scan, keep_discovering=True)
                    break
        except Exception as e:
            msg = str(e)
            if "UnknownObject" in msg or "doesn't exist" in msg:
                print(
                    "    device disappeared from BlueZ before the connection completed."
                )
                print("    Press r to rescan and select it again.")
            else:
                print(f"    error: {msg}")
        finally:
            if sess is not None:
                sess.close()
                print("  disconnected")


if __name__ == "__main__":
    sys.exit(main())
