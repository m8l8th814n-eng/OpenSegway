#!/usr/bin/env python3

"""Menu client for BleTool locks, ZK600 shell, and general GATT exploration."""

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
        ORDER_FW,
        build,
        parse,
        key_payload,
        open_payload,
    )
    from nb_client2 import pump, scan, show, fresh_connect, dbus_interface
except ImportError as e:
    sys.exit(
        f"missing sibling modules: {e}\n"
        "nb_client.py, nb_client2.py, and nb_client3.py must be "
        "in the same directory."
    )


DEVICE_KEYS = ["4BKNwi77", "yOTmK50z", "OmniW4GX", "Vgz7"]

UUID_LOCK = (
    "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
    "6e400003-b5a3-f393-e0a9-e50e24dcca9e",
)
UUID_SHELL = (
    "0000ff02-0000-1000-8000-00805f9b34fb",
    "0000ff03-0000-1000-8000-00805f9b34fb",
)


def ask(prompt, default=""):
    try:
        s = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return s or default


def full_uuid(short):

    u = short.lower()
    if len(u) == 4:
        return f"0000{u}-0000-1000-8000-00805f9b34fb"
    return u


def find_chars(root, write_uuid, notify_uuid, timeout=15):
    write_path = notify_path = None
    deadline = time.time() + timeout
    while time.time() < deadline and (write_path is None or notify_path is None):
        for path, ifaces in root.GetManagedObjects().items():
            if "org.bluez.GattCharacteristic1" not in ifaces:
                continue
            u = str(ifaces["org.bluez.GattCharacteristic1"].get("UUID", "")).lower()
            if u == write_uuid:
                write_path = str(path)
            elif u == notify_uuid:
                notify_path = str(path)
        if write_path is None or notify_path is None:
            pump(0.4)
    return write_path, notify_path


class Session:

    def __init__(self, bus, write_path, notify_path):
        import dbus

        self.bus = bus
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

    def _write(self, payload):
        import dbus

        self.write.WriteValue(
            dbus.Array(payload, signature="y"), dbus.Dictionary({}, signature="sv")
        )

    def send(self, order, payload, label, reply_timeout=5.0):
        frame = build(order, payload, self.key)
        print(f"    -> order={order:>3} {label:14s} {frame.hex()}")
        self._write(frame)
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

    def send_text(self, line, settle=1.0):
        if line[:3].lower() == "hex" or line.startswith("0x"):
            hx = line.split()[-1] if " " in line else line[2:]
            data = bytes.fromhex(hx)
            print(f"    -> hex {data.hex()}")
        else:
            data = (line + "\r\n").encode("utf-8")
            if line:
                print(f"    -> {line!r}")
        if data:
            self._write(data)
        pump(settle)
        self.drain()

    def drain(self):
        while self.inbox:
            value = self.inbox.pop(0)
            try:
                txt = value.decode("utf-8", errors="strict").strip("\r\n\0")
                print(f"    <- {txt!r}")
            except UnicodeDecodeError:
                print(f"    <- (binary) {value.hex()}")

    def close(self, dev):
        try:
            self.notify.StopNotify()
        except Exception:
            pass
        try:
            dev.Disconnect()
        except Exception:
            pass


def pick_device(bus, adapter_iface, root, scan_seconds=12.0):
    devs = scan(bus, adapter_iface, root, scan_seconds, keep_discovering=True)
    if not devs:
        print("no devices found")
        return None
    while True:
        show(devs)
        val = ask("select a number (r = rescan, q = quit): ")
        if val is None or val in ("q", ""):
            return None
        if val == "r":
            devs = scan(bus, adapter_iface, root, scan_seconds, keep_discovering=True)
            if not devs:
                print("no devices found")
            continue
        if not val.isdigit() or not (1 <= int(val) <= len(devs)):
            print("invalid selection")
            continue
        try:
            adapter_iface.StopDiscovery()
        except Exception:
            pass
        return devs[int(val) - 1]


def connect_and_session(bus, adapter_iface, root, target, write_uuid, notify_uuid):
    dev = fresh_connect(adapter_iface, bus, root, target["addr"], target["name"])
    if dev is None:
        return None, None
    write_path, notify_path = find_chars(root, write_uuid, notify_uuid)
    if not (write_path and notify_path):
        print(f"    could not find {write_uuid[:20]}... on the device")
        try:
            dev.Disconnect()
        except Exception:
            pass
        return None, None
    sess = Session(bus, write_path, notify_path)
    print("    subscribing to notifications")
    return dev, sess


def pick_key():
    print("    keys from the app:")
    for i, k in enumerate(DEVICE_KEYS, 1):
        print(f"      {i} = {k}")
    v = ask("    select [1-4 or custom, enter=1]: ", "1")
    if v is None:
        return None
    if v.isdigit() and 1 <= int(v) <= len(DEVICE_KEYS):
        return DEVICE_KEYS[int(v) - 1]
    return v


def mode_lock(bus, adapter_iface, root, target):
    dev, sess = connect_and_session(bus, adapter_iface, root, target, *UUID_LOCK)
    if not sess:
        return
    device_key = pick_key()
    if device_key is None:
        sess.close(dev)
        return
    try:
        sess.handshake(device_key)
        while True:
            cmd = ask(
                "  [u]nlock [l]ock [s]tatus [f] vehicle info firm[w]are "
                "[k] change key+handshake [a]nother device [q] > ",
                "q",
            )
            if cmd is None or cmd in ("q", ""):
                return
            if cmd == "u":
                sess.send(ORDER_OPEN, open_payload(int(time.time())), "UNLOCK")
            elif cmd == "l":
                sess.send(ORDER_CLOSE, open_payload(int(time.time())), "LOCK")
            elif cmd == "s":
                sess.send(ORDER_INFO, bytes(1), "status")
            elif cmd == "f":
                sess.send(ORDER_SCOOTER_INFO, bytes(8), "vehicle info")
            elif cmd == "w":
                sess.send(ORDER_FW, bytes(1), "firmware-info")
            elif cmd == "k":
                k2 = pick_key()
                if k2:
                    device_key = k2
                    sess.key = 0x00
                    sess.handshake(device_key)
            elif cmd == "a":
                return
            sess.drain()
    finally:
        sess.close(dev)
        print("  disconnected")


def mode_shell(bus, adapter_iface, root, target):
    dev, sess = connect_and_session(bus, adapter_iface, root, target, *UUID_SHELL)
    if not sess:
        return
    try:
        pump(1.0)
        sess.drain()
        print("    text+enter sends CRLF; 'hex aabb' = raw bytes;")
        print("    empty line = read only; q = back. Start with enter / 'help'.")
        while True:
            line = ask("  shell> ")
            if line is None or line in ("q", "quit", "exit"):
                return
            sess.send_text(line)
    finally:
        sess.close(dev)
        print("  disconnected")


def list_gatt(root):

    chars = []
    svc_of = {}
    for path, ifaces in root.GetManagedObjects().items():
        if "org.bluez.GattService1" in ifaces:
            svc_of[str(path)] = str(ifaces["org.bluez.GattService1"].get("UUID", ""))
    for path, ifaces in root.GetManagedObjects().items():
        if "org.bluez.GattCharacteristic1" not in ifaces:
            continue
        p = ifaces["org.bluez.GattCharacteristic1"]
        chars.append(
            (
                str(path),
                svc_of.get(str(p.get("Service", "")), "?"),
                str(p.get("UUID", "")),
                ",".join(str(f) for f in p.get("Flags", [])),
            )
        )
    return chars


def show_gatt(chars):
    print(f"\n{'#':>3}  {'service':38s} {'char':38s} flags")
    print("-" * 100)
    for i, (path, svc, u, flags) in enumerate(chars, 1):
        print(f"{i:>3}  {svc:38s} {u:38s} {flags}")
    print()


def mode_explore(bus, adapter_iface, root, target):
    dev = fresh_connect(adapter_iface, bus, root, target["addr"], target["name"])
    if dev is None:
        return
    subs = {}
    try:
        chars = list_gatt(root)
        if not chars:
            print("    no characteristics visible")
            return
        show_gatt(chars)
        print("    commands: l N=read, w N=write hex, n N=toggle notify,")
        print("    g=refresh list, q=back")
        import dbus

        while True:
            line = ask("  gatt> ", "q")
            if line is None or line in ("q", ""):
                return
            parts = line.split(maxsplit=1)
            op = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            if op == "g":
                chars = list_gatt(root)
                show_gatt(chars)
                continue
            idx_s, hx = (rest.split("=", 1) + [""])[:2] if "=" in rest else (rest, "")
            if not idx_s.isdigit() or not (1 <= int(idx_s) <= len(chars)):
                print("    invalid - e.g. 'l 3', 'w 5=a3a4', 'n 5'")
                continue
            idx = int(idx_s)
            path = chars[idx - 1][0]
            ch = dbus.Interface(
                bus.get_object("org.bluez", path), "org.bluez.GattCharacteristic1"
            )
            if op == "l":
                try:
                    val = bytes(
                        bytearray(ch.ReadValue(dbus.Dictionary({}, signature="sv")))
                    )
                    print(f"    <- {val.hex()}  {val!r}")
                except Exception as e:
                    print(f"    read error: {e}")
            elif op == "w":
                if not hx:
                    print("    format: w N=aabbcc")
                    continue
                try:
                    data = bytes.fromhex(hx)
                    ch.WriteValue(
                        dbus.Array(data, signature="y"),
                        dbus.Dictionary({}, signature="sv"),
                    )
                    print(f"    -> {data.hex()}")
                except Exception as e:
                    print(f"    write error: {e}")
            elif op == "n":
                if idx in subs:
                    try:
                        subs[idx][0].StopNotify()
                    except Exception:
                        pass
                    bus.remove_signal_receiver(subs[idx][1])
                    del subs[idx]
                    print("    notify OFF")
                else:

                    def mk_printer(tag):
                        def rx(iface, changed, invalidated, path=None):
                            if "Value" in changed:
                                v = bytes(bytearray(changed["Value"]))
                                print(f"    <-[{tag}] {v.hex()} {v!r}")

                        return rx

                    rx = mk_printer(idx)
                    try:
                        bus.add_signal_receiver(
                            rx,
                            dbus_interface="org.freedesktop.DBus.Properties",
                            signal_name="PropertiesChanged",
                            path=path,
                        )
                        ch.StartNotify()
                        subs[idx] = (ch, rx)
                        print(
                            "    notify ON  (commands still work; "
                            "values are printed as they arrive)"
                        )
                    except Exception as e:
                        bus.remove_signal_receiver(rx)
                        print(f"    notify error: {e}")
            pump(0.3)
    finally:
        for ch, rx in subs.values():
            try:
                ch.StopNotify()
            except Exception:
                pass
            try:
                bus.remove_signal_receiver(rx)
            except Exception:
                pass
        try:
            dev.Disconnect()
        except Exception:
            pass
        print("  disconnected")


def main():
    ap = argparse.ArgumentParser(description="BLE menu client (BleTool/ZK600)")
    ap.add_argument("--adapter", default="hci0")
    a = ap.parse_args()

    print("nb_client3 - select a function:")
    print("  1 = BleTool lock (Omni A3A4 / NUS)")
    print("  2 = ZK600 serial shell (ff02/ff03)")
    print("  3 = GATT explorer (unknown device)")
    v = ask("function [1/2/3]: ", "1")
    if v is None:
        return 0
    mode = {"1": "lock", "2": "shell", "3": "gatt"}.get(v)
    if mode is None:
        print("invalid selection")
        return 2

    try:
        import dbus
        import dbus.mainloop.glib
    except ImportError:
        sys.exit(
            "missing dbus-python/PyGObject - run with the system python3 "
            "(tsu + /usr/bin/python3)."
        )
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_iface = dbus_interface(
        bus.get_object("org.bluez", f"/org/bluez/{a.adapter}"), "org.bluez.Adapter1"
    )
    root = dbus_interface(
        bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager"
    )

    while True:
        target = pick_device(bus, adapter_iface, root)
        if target is None:
            return 0
        print(f"\nselected {target['name']!r} ({target['addr']})")
        if target["rssi"] is not None and target["rssi"] < -90:
            print(f"    warning: weak signal ({target['rssi']} dBm)")
        try:
            if mode == "lock":
                mode_lock(bus, adapter_iface, root, target)
            elif mode == "shell":
                mode_shell(bus, adapter_iface, root, target)
            else:
                mode_explore(bus, adapter_iface, root, target)
        except Exception as e:
            print(f"    error: {e}")
        if ask("connect to another device? [y/N]: ", "n") not in ("y", "yes"):
            return 0


if __name__ == "__main__":
    sys.exit(main())
