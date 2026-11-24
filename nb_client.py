#!/usr/bin/env python3

"""BLE client for Omni locks. Requires dbus-python and PyGObject."""

import argparse
import sys
import time

WRITE_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

ORDER_KEY = 1
ORDER_OPEN = 5
ORDER_CLOSE = 21
ORDER_INFO = 49
ORDER_SCOOTER_INFO = 96
ORDER_FW = 250


CRC8_TABLE = [
    0x00, 0x5E, 0xBC, 0xE2, 0x61, 0x3F, 0xDD, 0x83, 0xC2, 0x9C, 0x7E, 0x20, 0xA3, 0xFD, 0x1F, 0x41,
    0x9D, 0xC3, 0x21, 0x7F, 0xFC, 0xA2, 0x40, 0x1E, 0x5F, 0x01, 0xE3, 0xBD, 0x3E, 0x60, 0x82, 0xDC,
    0x23, 0x7D, 0x9F, 0xC1, 0x42, 0x1C, 0xFE, 0xA0, 0xE1, 0xBF, 0x5D, 0x03, 0x80, 0xDE, 0x3C, 0x62,
    0xBE, 0xE0, 0x02, 0x5C, 0xDF, 0x81, 0x63, 0x3D, 0x7C, 0x22, 0xC0, 0x9E, 0x1D, 0x43, 0xA1, 0xFF,
    0x46, 0x18, 0xFA, 0xA4, 0x27, 0x79, 0x9B, 0xC5, 0x84, 0xDA, 0x38, 0x66, 0xE5, 0xBB, 0x59, 0x07,
    0xDB, 0x85, 0x67, 0x39, 0xBA, 0xE4, 0x06, 0x58, 0x19, 0x47, 0xA5, 0xFB, 0x78, 0x26, 0xC4, 0x9A,
    0x65, 0x3B, 0xD9, 0x87, 0x04, 0x5A, 0xB8, 0xE6, 0xA7, 0xF9, 0x1B, 0x45, 0xC6, 0x98, 0x7A, 0x24,
    0xF8, 0xA6, 0x44, 0x1A, 0x99, 0xC7, 0x25, 0x7B, 0x3A, 0x64, 0x86, 0xD8, 0x5B, 0x05, 0xE7, 0xB9,
    0x8C, 0xD2, 0x30, 0x6E, 0xED, 0xB3, 0x51, 0x0F, 0x4E, 0x10, 0xF2, 0xAC, 0x2F, 0x71, 0x93, 0xCD,
    0x11, 0x4F, 0xAD, 0xF3, 0x70, 0x2E, 0xCC, 0x92, 0xD3, 0x8D, 0x6F, 0x31, 0xB2, 0xEC, 0x0E, 0x50,
    0xAF, 0xF1, 0x13, 0x4D, 0xCE, 0x90, 0x72, 0x2C, 0x6D, 0x33, 0xD1, 0x8F, 0x0C, 0x52, 0xB0, 0xEE,
    0x32, 0x6C, 0x8E, 0xD0, 0x53, 0x0D, 0xEF, 0xB1, 0xF0, 0xAE, 0x4C, 0x12, 0x91, 0xCF, 0x2D, 0x73,
    0xCA, 0x94, 0x76, 0x28, 0xAB, 0xF5, 0x17, 0x49, 0x08, 0x56, 0xB4, 0xEA, 0x69, 0x37, 0xD5, 0x8B,
    0x57, 0x09, 0xEB, 0xB5, 0x36, 0x68, 0x8A, 0xD4, 0x95, 0xCB, 0x29, 0x77, 0xF4, 0xAA, 0x48, 0x16,
    0xE9, 0xB7, 0x55, 0x0B, 0x88, 0xD6, 0x34, 0x6A, 0x2B, 0x75, 0x97, 0xC9, 0x4A, 0x14, 0xF6, 0xA8,
    0x74, 0x2A, 0xC8, 0x96, 0x15, 0x4B, 0xA9, 0xF7, 0xB6, 0xE8, 0x0A, 0x54, 0xD7, 0x89, 0x6B, 0x35,
]


def crc8(data: bytes) -> int:
    i = 0
    for b in data:
        i = CRC8_TABLE[(i ^ b) & 0xFF]
    return i


def build(
    order: int, payload: bytes, session_key: int = 0x00, xor_key: int = 0x19
) -> bytes:

    dec = (
        bytes(
            [0xA3, 0xA4, len(payload) & 0xFF, xor_key, session_key & 0xFF, order & 0xFF]
        )
        + payload
    )
    out = bytearray(dec)
    out[3] = (xor_key + 50) & 0xFF
    for k in range(4, len(out)):
        out[k] = dec[k] ^ xor_key
    return bytes(out) + bytes([crc8(bytes(out))])


def parse(value: bytes):

    i3 = 0
    i = 0
    while i3 < len(value):
        if value[i3] == 0xA3 and value[i3 + 1] == 0xA4:
            i = value[i3 + 2] + 7
            break
        i3 += 1
    if i == 0:
        return None, "no A3 A4 frame"
    fr = value[i3 : i3 + i]
    body = fr[:-1]
    if crc8(body) != fr[-1]:
        return None, f"CRC8 error (calculated {crc8(body):02X}, frame has {fr[-1]:02X})"
    b = (fr[3] - 50) & 0xFF
    dec = bytearray(body)
    dec[3] = b
    for k in range(4, len(dec)):
        dec[k] = body[k] ^ b
    return dec[5], bytes(dec)


def pump(seconds):

    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    deadline = time.time() + seconds
    while time.time() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def key_payload(device_key: str) -> bytes:
    raw = device_key.encode()[:8]
    return raw + bytes(8 - len(raw))


def open_payload(timestamp: int) -> bytes:

    return (
        bytes([1]) + bytes(4) + timestamp.to_bytes(4, "big", signed=False) + bytes([0])
    )


def run(name, device_key, adapter, actions, scan_timeout, reply_timeout):
    import dbus
    import dbus.mainloop.glib

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_path = f"/org/bluez/{adapter}"

    aobj = bus.get_object("org.bluez", adapter_path)
    adapter_iface = dbus.Interface(aobj, "org.bluez.Adapter1")

    root = dbus.Interface(
        bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager"
    )

    print(f"[1] Scanning for {name!r} on {adapter} ...")

    try:
        adapter_iface.SetDiscoveryFilter({"Transport": "le"})
    except dbus.exceptions.DBusException as e:
        print(f"    (could not set LE filter: {e.get_dbus_name()})")
    try:
        adapter_iface.StartDiscovery()
    except dbus.exceptions.DBusException as e:
        nm = e.get_dbus_name()
        if "InProgress" in nm or "Already" in nm:
            print("    (scan already in progress)")
        else:
            print(f"    StartDiscovery failed: {nm}")
            return 1

    dev_path = None
    deadline = time.time() + scan_timeout
    while time.time() < deadline and dev_path is None:
        for path, ifaces in root.GetManagedObjects().items():
            if "org.bluez.Device1" not in ifaces:
                continue
            p = ifaces["org.bluez.Device1"]
            alias = str(p.get("Alias", ""))
            dname = str(p.get("Name", ""))
            if alias == name or dname == name:
                dev_path = str(path)
                print(f"    found {alias!r} at {path}")
                break
        if dev_path is None:
            pump(0.5)
    try:
        adapter_iface.StopDiscovery()
    except dbus.exceptions.DBusException:
        pass
    if dev_path is None:
        print(f"    did not find {name!r} within {scan_timeout}s")
        return 1

    print("[2] Connecting ...")

    def try_connect(path, label):
        obj = bus.get_object("org.bluez", path)
        d = dbus.Interface(obj, "org.bluez.Device1")
        pr = dbus.Interface(obj, "org.freedesktop.DBus.Properties")

        for at in ("public", "random"):
            try:
                pr.Set("org.bluez.Device1", "AddressType", at)
                break
            except dbus.exceptions.DBusException:
                continue
        print(f"    {label}: Connect() ...")
        d.Connect()
        return d

    dev = None
    try:
        dev = try_connect(dev_path, "attempt 1")
    except dbus.exceptions.DBusException as e:
        nm = e.get_dbus_name()
        print(f"    failed: {nm}")
        if "page-timeout" in str(e) or "Failed" in nm or "key-missing" in str(e):

            print("    rescanning with LE filter and retrying ...")
            try:
                adapter_iface.SetDiscoveryFilter({"Transport": "le"})
            except dbus.exceptions.DBusException:
                pass
            try:
                adapter_iface.StartDiscovery()
            except dbus.exceptions.DBusException:
                pass
            dev_path = None
            deadline = time.time() + scan_timeout
            while time.time() < deadline and dev_path is None:
                for path, ifaces in root.GetManagedObjects().items():
                    if "org.bluez.Device1" not in ifaces:
                        continue
                    pp = ifaces["org.bluez.Device1"]
                    if name in (str(pp.get("Alias", "")), str(pp.get("Name", ""))):
                        dev_path = str(path)
                        break
                if dev_path is None:
                    time.sleep(0.5)
            try:
                adapter_iface.StopDiscovery()
            except dbus.exceptions.DBusException:
                pass
            if dev_path is None:
                print("    could not find it again - is fake_lock running on the other machine?")
                return 1
            print(f"    rediscovered: {dev_path}")
            try:
                dev = try_connect(dev_path, "attempt 2")
            except dbus.exceptions.DBusException as e2:
                print(f"    failed again: {e2.get_dbus_name()}")
                print(
                    "    Make sure fake_lock shows '[4] advertising' and is within range."
                )
                return 1
    if dev is None:
        return 1

    write_path = notify_path = None
    deadline = time.time() + 15
    while time.time() < deadline and (write_path is None or notify_path is None):
        for path, ifaces in root.GetManagedObjects().items():
            if "org.bluez.GattCharacteristic1" not in ifaces:
                continue
            p = ifaces["org.bluez.GattCharacteristic1"]
            u = str(p.get("UUID", "")).lower()
            if u == WRITE_UUID:
                write_path = str(path)
            elif u == NOTIFY_UUID:
                notify_path = str(path)
        if write_path is None or notify_path is None:
            pump(0.5)
    if write_path is None or notify_path is None:
        print("    could not find the service characteristics - is the device running fake_lock?")
        dev.Disconnect()
        return 1

    print("[3] Subscribing to notifications")
    notify = dbus.Interface(
        bus.get_object("org.bluez", notify_path), "org.bluez.GattCharacteristic1"
    )
    write = dbus.Interface(
        bus.get_object("org.bluez", write_path), "org.bluez.GattCharacteristic1"
    )

    inbox = []

    def on_props_changed(iface, changed, invalidated, path=None):
        if path is not None and str(path) != notify_path:
            return
        if "Value" in changed:
            inbox.append(bytes(bytearray(changed["Value"])))

    bus.add_signal_receiver(
        on_props_changed,
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        path=notify_path,
    )
    notify.StartNotify()
    pump(0.5)

    session = {"key": 0x00}

    def send(order, payload, label):
        frame = build(order, payload, session["key"])
        print(f"    -> sending order={order} ({label}) {frame.hex()}")
        write.WriteValue(
            dbus.Array(frame, signature="y"), dbus.Dictionary({}, signature="sv")
        )
        deadline = time.time() + reply_timeout
        while time.time() < deadline:
            while inbox:
                value = inbox.pop(0)
                o, dec = parse(value)
                if o is None:
                    print(f"       <reply could not be decoded: {dec}>")
                    continue
                ln = dec[2]
                pl = dec[6 : 6 + ln]
                print(
                    f"       <- reply order={o} status={dec[6]} key=0x{dec[4]:02X} "
                    f"payload={pl.hex()}"
                )
                return o, dec
            pump(0.05)
        print(f"       (no reply within {reply_timeout}s)")
        return None, None

    print(f"[4] Handshake with deviceKey {device_key!r}")
    _, dec = send(ORDER_KEY, key_payload(device_key), "key request")
    if dec is None:
        print("    no reply - aborting")
        dev.Disconnect()
        return 1
    if dec[6] != 1:
        print(f"    device rejected the key (status={dec[6]})")
        dev.Disconnect()
        return 1
    session["key"] = dec[7]
    print(f"    OK. session key = 0x{session['key']:02X}")

    for action in actions:
        if action == "unlock":
            send(ORDER_OPEN, open_payload(int(time.time())), "UNLOCK")
        elif action == "lock":
            send(ORDER_CLOSE, open_payload(int(time.time())), "LOCK")
        elif action == "info":
            send(ORDER_SCOOTER_INFO, bytes(8), "vehicle info")
        elif action == "status":
            send(ORDER_INFO, bytes(1), "status")
        time.sleep(0.3)

    print("[5] Disconnecting")
    try:
        notify.StopNotify()
    except Exception:
        pass
    dev.Disconnect()
    return 0


def main():
    ap = argparse.ArgumentParser(description="BLE central for fake_lock.py")
    ap.add_argument("--name", default="Segway IoT", help="advertised device name")
    ap.add_argument("--key", default="4BKNwi77", help="deviceKey to send")
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument("--scan-timeout", type=float, default=20.0)
    ap.add_argument("--reply-timeout", type=float, default=5.0)
    ap.add_argument(
        "--lock", action="store_true", help="lock instead of unlocking"
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="handshake + unlock + lock + vehicle info + status",
    )
    a = ap.parse_args()

    if a.all:
        actions = ["unlock", "info", "lock", "status"]
    elif a.lock:
        actions = ["lock"]
    else:
        actions = ["unlock"]

    try:
        return run(a.name, a.key, a.adapter, actions, a.scan_timeout, a.reply_timeout)
    except ImportError:
        sys.exit(
            "missing dbus-python/PyGObject. Packages: python3-dbus python3-gi\n"
            "Run with the system python3."
        )


if __name__ == "__main__":
    sys.exit(main())
