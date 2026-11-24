#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nb_client3.py - menyklient for allt runt BleTool/ZK600.

Vid start valjs funktion (1/2/3) - forsta valet nar skriptet kors:

  1 = BleTool-las (Omni A3A4 over NUS 6E400001): handskakning, las upp/las,
      status, fordonsinfo, firmware-info, nyckelbyte. Samma protokoll som
      appens scooter_nb-verktyg - bra bade mot fake_lock.py och riktigt las.
  2 = ZK600 serial shell (ff02 write / ff03 notify): ra text/hex in, text ut.
      Shellen syns i boot-loggen 2026-10-17 (STATUS.md 9). Hypotesen att den
      kan andra MQTT-endpoint ar obevisad - borja med enter / 'help'.
  3 = GATT-utforskare: lista alla services/karakteristiker, las, skriv hex,
      sla notify av/pa pa valfri characteristic. For okanda enheter.

Bygger pa nb_client.py (A3A4-protokoll, ramar, CRC) och nb_client2.py
(scan/anslut/pump) - alla tre maste ligga i samma katalog.
Termux: kor med root (tsu). dbus-python + PyGObject kravs.

  sudo python3 nb_client3.py [--adapter hci0]
"""
import argparse
import sys
import time

try:
    from nb_client import (ORDER_KEY, ORDER_OPEN, ORDER_CLOSE, ORDER_INFO,
                           ORDER_SCOOTER_INFO, ORDER_FW,
                           build, parse, key_payload, open_payload)
    from nb_client2 import (pump, scan, show, resolve_path, fresh_connect,
                            dbus_interface)
except ImportError as e:
    sys.exit(f"saknar broderna: {e}\n"
             "nb_client.py, nb_client2.py och nb_client3.py maste ligga "
             "i samma katalog.")

# Nycklar som hittats i appen (STATUS.md 8). Anvands vid handskakning.
NYCKLAR = ["4BKNwi77", "yOTmK50z", "OmniW4GX", "Vgz7"]

UUID_LAS = ("6e400002-b5a3-f393-e0a9-e50e24dcca9e",
            "6e400003-b5a3-f393-e0a9-e50e24dcca9e")
UUID_SHELL = ("0000ff02-0000-1000-8000-00805f9b34fb",
              "0000ff03-0000-1000-8000-00805f9b34fb")


# ----------------------------------------------------------------- gemensamt

def ask(prompt, default=""):
    try:
        s = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return s or default


def full_uuid(short):
    """'ff02' -> '0000ff02-0000-1000-8000-00805f9b34fb'; full form rors ej."""
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
    """Anslutning + notify-prenumeration pa ett valt UUID-par."""
    def __init__(self, bus, write_path, notify_path):
        import dbus
        self.bus = bus
        self.inbox = []
        self.key = 0x00
        self.write = dbus.Interface(bus.get_object("org.bluez", write_path),
                                    "org.bluez.GattCharacteristic1")
        self.notify = dbus.Interface(bus.get_object("org.bluez", notify_path),
                                     "org.bluez.GattCharacteristic1")
        self.notify_path = notify_path

        def on_change(iface, changed, invalidated, path=None):
            if path is not None and str(path) != self.notify_path:
                return
            if "Value" in changed:
                self.inbox.append(bytes(bytearray(changed["Value"])))
        bus.add_signal_receiver(on_change,
                                dbus_interface="org.freedesktop.DBus.Properties",
                                signal_name="PropertiesChanged",
                                path=notify_path)
        self.notify.StartNotify()
        pump(0.5)

    def _write(self, payload):
        import dbus
        self.write.WriteValue(dbus.Array(payload, signature="y"),
                              dbus.Dictionary({}, signature="sv"))

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
                    print(f"       <odekodbart svar: {dec}>")
                    continue
                pl = dec[6:6 + dec[2]]
                print(f"       <- order={o:>3} status={dec[6]} nyckel=0x{dec[4]:02X} "
                      f"payload={pl.hex()}")
                return o, dec
            pump(0.05)
        print("       (inget svar)")
        return None, None

    def handshake(self, device_key):
        print(f"    handskakning med deviceKey {device_key!r}")
        _, dec = self.send(ORDER_KEY, key_payload(device_key), "nyckel")
        if dec is None or dec[6] != 1:
            print("    ingen giltig nyckel tillbaka")
            return False
        self.key = dec[7]
        print(f"    OK - sessionsnyckel 0x{self.key:02X}")
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
                print(f"    <- (binart) {value.hex()}")

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
        print("hittade inga enheter")
        return None
    while True:
        show(devs)
        val = ask("valj nummer (r = skanna om, q = avsluta): ")
        if val is None or val in ("q", ""):
            return None
        if val == "r":
            devs = scan(bus, adapter_iface, root, scan_seconds, keep_discovering=True)
            if not devs:
                print("hittade inga enheter")
            continue
        if not val.isdigit() or not (1 <= int(val) <= len(devs)):
            print("ogiltigt val")
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
        print(f"    hittade inte {write_uuid[:20]}... pa enheten")
        try:
            dev.Disconnect()
        except Exception:
            pass
        return None, None
    sess = Session(bus, write_path, notify_path)
    print("    prenumererar pa notify")
    return dev, sess


# ------------------------------------------------------- 1: BleTool-las

def pick_key():
    print("    nycklar ur appen:")
    for i, k in enumerate(NYCKLAR, 1):
        print(f"      {i} = {k}")
    v = ask("    valj [1-4 eller egen, enter=1]: ", "1")
    if v is None:
        return None
    if v.isdigit() and 1 <= int(v) <= len(NYCKLAR):
        return NYCKLAR[int(v) - 1]
    return v


def mode_lock(bus, adapter_iface, root, target):
    dev, sess = connect_and_session(bus, adapter_iface, root, target, *UUID_LAS)
    if not sess:
        return
    device_key = pick_key()
    if device_key is None:
        sess.close(dev)
        return
    try:
        sess.handshake(device_key)
        while True:
            cmd = ask("  [u]pplas [l]as [s]tatus [f]ordonsinfo firm[w]are "
                      "[k] byt nyckel+handsaka [a]nnu en enhet [q] > ", "q")
            if cmd is None or cmd in ("q", ""):
                return
            if cmd == "u":
                sess.send(ORDER_OPEN, open_payload(int(time.time())), "LAS UPP")
            elif cmd == "l":
                sess.send(ORDER_CLOSE, open_payload(int(time.time())), "LAS")
            elif cmd == "s":
                sess.send(ORDER_INFO, bytes(1), "status")
            elif cmd == "f":
                sess.send(ORDER_SCOOTER_INFO, bytes(8), "fordonsinfo")
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
        print("  nerkopplad")


# ---------------------------------------------------- 2: ZK600 serial shell

def mode_shell(bus, adapter_iface, root, target):
    dev, sess = connect_and_session(bus, adapter_iface, root, target, *UUID_SHELL)
    if not sess:
        return
    try:
        pump(1.0)
        sess.drain()   # ev. banner eller prompt
        print("    text+enter skickar med CRLF; 'hex aabb' = rabyte;")
        print("    tom rad = bara las; q = tillbaka. Borja med enter / 'help'.")
        while True:
            line = ask("  shell> ")
            if line is None or line in ("q", "quit", "exit"):
                return
            sess.send_text(line)
    finally:
        sess.close(dev)
        print("  nerkopplad")


# ------------------------------------------------------ 3: GATT-utforskare

def list_gatt(root, adapter):
    """Returnera [(char_path, service_uuid, uuid, flags)] for ansluten enhet."""
    chars = []
    svc_of = {}
    for path, ifaces in root.GetManagedObjects().items():
        if "org.bluez.GattService1" in ifaces:
            svc_of[str(path)] = str(ifaces["org.bluez.GattService1"].get("UUID", ""))
    for path, ifaces in root.GetManagedObjects().items():
        if "org.bluez.GattCharacteristic1" not in ifaces:
            continue
        p = ifaces["org.bluez.GattCharacteristic1"]
        chars.append((str(path),
                      svc_of.get(str(p.get("Service", "")), "?"),
                      str(p.get("UUID", "")),
                      ",".join(str(f) for f in p.get("Flags", []))))
    return chars


def show_gatt(chars):
    print(f"\n{'#':>3}  {'service':38s} {'char':38s} flaggor")
    print("-" * 100)
    for i, (path, svc, u, flags) in enumerate(chars, 1):
        print(f"{i:>3}  {svc:38s} {u:38s} {flags}")
    print()


def mode_explore(bus, adapter_iface, root, target):
    dev = fresh_connect(adapter_iface, bus, root, target["addr"], target["name"])
    if dev is None:
        return
    subs = {}   # idx -> (iface, receiver) for StoppNotify vid behov
    try:
        chars = list_gatt(root, adapter_iface)
        if not chars:
            print("    inga karakteristiker synliga")
            return
        show_gatt(chars)
        print("    kommandon: l N=las, w N=skriv hex, n N=notify av/pa,")
        print("    g=lista om, q=tillbaka")
        import dbus
        while True:
            line = ask("  gatt> ", "q")
            if line is None or line in ("q", ""):
                return
            parts = line.split(maxsplit=1)
            op = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            if op == "g":
                chars = list_gatt(root, adapter_iface)
                show_gatt(chars)
                continue
            idx_s, hx = (rest.split("=", 1) + [""])[:2] if "=" in rest else (rest, "")
            if not idx_s.isdigit() or not (1 <= int(idx_s) <= len(chars)):
                print("    ogiltigt - t.ex. 'l 3', 'w 5=a3a4', 'n 5'")
                continue
            idx = int(idx_s)
            path = chars[idx - 1][0]
            ch = dbus.Interface(bus.get_object("org.bluez", path),
                                "org.bluez.GattCharacteristic1")
            if op == "l":
                try:
                    val = bytes(bytearray(ch.ReadValue(
                        dbus.Dictionary({}, signature="sv"))))
                    print(f"    <- {val.hex()}  {val!r}")
                except Exception as e:
                    print(f"    lasfel: {e}")
            elif op == "w":
                if not hx:
                    print("    format: w N=aabbcc")
                    continue
                try:
                    data = bytes.fromhex(hx)
                    ch.WriteValue(dbus.Array(data, signature="y"),
                                  dbus.Dictionary({}, signature="sv"))
                    print(f"    -> {data.hex()}")
                except Exception as e:
                    print(f"    skrivfel: {e}")
            elif op == "n":
                if idx in subs:
                    try:
                        subs[idx][0].StopNotify()
                    except Exception:
                        pass
                    bus.remove_signal_receiver(subs[idx][1])
                    del subs[idx]
                    print("    notify AV")
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
                            signal_name="PropertiesChanged", path=path)
                        ch.StartNotify()
                        subs[idx] = (ch, rx)
                        print(f"    notify PA  (kommandon gar fortfarande; "
                              f"varden skrivs ut nar de kommer)")
                    except Exception as e:
                        bus.remove_signal_receiver(rx)
                        print(f"    notifyfel: {e}")
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
        print("  nerkopplad")


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="BLE menyklient (BleTool/ZK600)")
    ap.add_argument("--adapter", default="hci0")
    a = ap.parse_args()

    print("nb_client3 - valj funktion:")
    print("  1 = BleTool-las (Omni A3A4 / NUS)")
    print("  2 = ZK600 serial shell (ff02/ff03)")
    print("  3 = GATT-utforskare (okand enhet)")
    v = ask("funktion [1/2/3]: ", "1")
    if v is None:
        return 0
    mode = {"1": "las", "2": "shell", "3": "gatt"}.get(v)
    if mode is None:
        print("ogiltigt val")
        return 2

    try:
        import dbus
        import dbus.mainloop.glib
        from gi.repository import GLib  # noqa: F401
    except ImportError:
        sys.exit("saknar dbus-python/PyGObject - kor med systemets python3 "
                 "(tsu + /usr/bin/python3).")
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_iface = dbus_interface(
        bus.get_object("org.bluez", f"/org/bluez/{a.adapter}"),
        "org.bluez.Adapter1")
    root = dbus_interface(bus.get_object("org.bluez", "/"),
                          "org.freedesktop.DBus.ObjectManager")

    while True:
        target = pick_device(bus, adapter_iface, root)
        if target is None:
            return 0
        print(f"\nvalde {target['name']!r} ({target['addr']})")
        if target["rssi"] is not None and target["rssi"] < -90:
            print(f"    varning: svag signal ({target['rssi']} dBm)")
        try:
            if mode == "las":
                mode_lock(bus, adapter_iface, root, target)
            elif mode == "shell":
                mode_shell(bus, adapter_iface, root, target)
            else:
                mode_explore(bus, adapter_iface, root, target)
        except Exception as e:
            print(f"    fel: {e}")
        if ask("anslut till annan enhet? [j/N]: ", "n") not in ("j", "ja", "y"):
            return 0


if __name__ == "__main__":
    sys.exit(main())
