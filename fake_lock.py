#!/usr/bin/env python3

"""BLE-perifer som emulerar Omni-lås för tester med BleTool."""

import argparse
import array
import sys


class _Tee:

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for st in self.streams:
            try:
                st.write(data)
                st.flush()
            except Exception:
                pass

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


BLUEZ = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
GATT_MANAGER = "org.bluez.GattManager1"
ADV_MANAGER = "org.bluez.LEAdvertisingManager1"

SVC_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
WRITE_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
NOTIFY_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

ORDER_KEY = 0x11
ORDER_UNLOCK = 0x21
ORDER_LOCK = 0x22
ORDER_STATUS = 0x31


T = [
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
]


def crc16_append(body: bytes) -> bytes:

    hi = 0xFF
    lo = 0xFF
    for b in body:
        idx = (lo ^ b) & 0xFF
        hi ^= T[idx]
        lo = T[idx]
    return bytes(body) + bytes([hi & 0xFF, lo & 0xFF])


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


def a3a4_decode(value: bytes):

    i3 = 0
    i = 0
    while i3 < len(value):
        if value[i3] == 163 and value[i3 + 1] == 164:
            i = value[i3 + 2] + 7
            break
        i3 += 1
    if i == 0:
        return None, "ingen A3 A4-ram"
    fr = value[i3 : i3 + i]
    body = fr[:-1]
    if crc8(body) != fr[-1]:
        return None, f"CRC8 fel (beraknad {crc8(body):02X}, i ramen {fr[-1]:02X})"
    b = (fr[3] - 50) & 0xFF
    dec = bytearray(body)
    dec[3] = b
    for k in range(4, len(dec)):
        dec[k] = body[k] ^ b
    return dec[5], bytes(dec)


def a3a4_reply(
    order: int,
    status: int,
    session_key: int,
    xor_key: int = 0x19,
    payload_len: int = 12,
) -> bytes:

    pl = bytearray(payload_len)

    if order == 1:
        pl[0] = status & 0xFF
        pl[1] = session_key & 0xFF
    elif order == 96:
        pl[0] = 87
        pl[1] = 1

    elif order == 251:

        pl[0] = 0

    elif order in (5, 21):
        pl[0] = 1
    else:
        pl[0] = status & 0xFF
    dec = bytes([0xA3, 0xA4, payload_len & 0xFF, xor_key, 0x00, order & 0xFF]) + bytes(
        pl
    )
    out = bytearray(dec)
    out[3] = (xor_key + 50) & 0xFF
    for k in range(4, len(out)):
        out[k] = dec[k] ^ xor_key
    return bytes(out) + bytes([crc8(bytes(out))])


def device_frame(order: int, key_bytes: bytes = b"", xor_key: int = 0x11) -> bytes:

    b = xor_key & 0xFF
    d = bytearray(10)
    d[0] = 0xFE
    d[1] = b
    d[2] = 0
    d[3] = order & 0xFF
    d[4] = 5
    for n, kb in enumerate(key_bytes):
        if 5 + n < len(d):
            d[5 + n] = kb & 0xFF
    frame = bytearray(x ^ b for x in d)
    frame[0] = 0xFE
    frame[1] = (b + 50) & 0xFF
    return crc16_append(bytes(frame))


def app_decode(wire: bytes):

    if len(wire) < 5 or wire[0] != 0xFE:
        return None, None
    rand = (wire[1] - 50) & 0xFF
    order = wire[3] ^ rand
    payload = bytes(wire[i] ^ rand for i in range(4, len(wire) - 1))
    return order, payload


def run_peripheral(name, expected_key, session_key, adapter, selftest_only=False):
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_path = f"/org/bluez/{adapter}"
    notify_holder = {"send": lambda payload: None}

    def on_write(value, options):
        data = bytes(bytearray(value))
        print(f"[write] raw={data.hex()}")

        order, dec = a3a4_decode(data)
        if order is not None:
            length = dec[2]
            payload = dec[6 : 6 + length]
            print(f"        familj=A3A4  order={order}")
            if order == 1:
                sent = payload.decode("utf-8", "replace").strip("\x00")
                hit = sent.startswith(expected_key)
                verdict = "MATCHAR" if hit else "MATCHAR INTE"
                print(
                    f"        handskakning - appen skickade nyckeln {sent!r} [{verdict}]"
                )
                reply = a3a4_reply(1, 1, session_key)
                notify_holder["send"](reply)
                print(
                    f"        -> svarade status=1 nyckel=0x{session_key:02X} "
                    f"({reply.hex()})"
                )
            elif order == 250:

                reply = a3a4_reply(251, 1, session_key)
                notify_holder["send"](reply)
                print(f"        firmware-info-begaran -> svarade 0xFB ({reply.hex()})")
            else:
                reply = a3a4_reply(order, 1, session_key)
                notify_holder["send"](reply)
                print(f"        -> svarade order={order} status=1 ({reply.hex()})")
            return

        order, payload = app_decode(data)
        if order is None:
            print(f"        (okand ramfamilj: {dec})")
            return
        print(f"        familj=FE  order=0x{order:02X}")
        if order == ORDER_KEY:
            sent = (
                payload[1:].decode("utf-8", "replace").strip("\x00")
                if len(payload) > 1
                else ""
            )
            verdict = "MATCHAR" if sent.startswith(expected_key) else "MATCHAR INTE"
            print(f"        nyckelbegaran - appen skickade {sent!r} [{verdict}]")
            notify_holder["send"](device_frame(ORDER_KEY, bytes([session_key])))
            print(f"        -> svarade 0x11 med sessionsnyckel 0x{session_key:02X}")
        elif order == ORDER_UNLOCK:
            print("        LAS UPP")
            notify_holder["send"](device_frame(ORDER_UNLOCK, bytes([session_key])))
            print("        -> svarade 0x21 (unlocked)")
        elif order == ORDER_LOCK:
            print("        LAS")
            notify_holder["send"](device_frame(ORDER_LOCK, bytes([session_key])))
        elif order == ORDER_STATUS:
            print("        lasstatus")
            notify_holder["send"](device_frame(ORDER_STATUS, bytes([session_key])))
        else:
            notify_holder["send"](device_frame(order, bytes([session_key])))
            print(f"        -> svarade order 0x{order:02X}")

    class Characteristic(dbus.service.Object):
        def __init__(self, index, uuid, flags, service_index):
            self.path = f"/org/bluez/fakelock/service{service_index}/char{index}"
            self.uuid = uuid
            self.flags = flags
            self.service_path = f"/org/bluez/fakelock/service{service_index}"
            self.notifying = False
            self.value = array.array("B", [])
            self.is_write = "write" in flags
            super().__init__(bus, self.path)

        def props(self):
            p = {
                "UUID": self.uuid,
                "Service": self.service_path,
                "Flags": dbus.Array(self.flags, signature="s"),
                "Value": dbus.Array(self.value, signature="y"),
            }
            if "notify" in self.flags:
                p["Notifying"] = dbus.Boolean(self.notifying)
            return p

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v"
        )
        def Get(self, iface, prop):
            return self.props()[prop]

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}"
        )
        def GetAll(self, iface):
            return dbus.Dictionary(self.props(), signature="sv")

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv")
        def Set(self, iface, prop, value):
            pass

        @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
        def PropertiesChanged(self, iface, changed, invalidated):
            pass

        @dbus.service.method(
            "org.bluez.GattCharacteristic1", in_signature="a{sv}", out_signature="ay"
        )
        def ReadValue(self, options):
            return dbus.Array(self.value, signature="y")

        @dbus.service.method("org.bluez.GattCharacteristic1", in_signature="aya{sv}")
        def WriteValue(self, value, options):
            if self.is_write:
                on_write(value, options)

        @dbus.service.method("org.bluez.GattCharacteristic1")
        def StartNotify(self):
            self.notifying = True
            print("[notify] appen PRENUMERERAR nu (StartNotify)")

        @dbus.service.method("org.bluez.GattCharacteristic1")
        def StopNotify(self):
            self.notifying = False
            print("[notify] appen SLUTAR prenumerera (StopNotify)")

    class Service(dbus.service.Object):
        def __init__(self, index, uuid, primary, chars):
            self.path = f"/org/bluez/fakelock/service{index}"
            self.uuid = uuid
            self.primary = primary
            self.chars = chars
            super().__init__(bus, self.path)

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v"
        )
        def Get(self, iface, prop):
            return self.GetAll(iface)[prop]

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}"
        )
        def GetAll(self, iface):
            return {
                "UUID": self.uuid,
                "Primary": dbus.Boolean(self.primary),
                "Characteristics": dbus.Array(
                    [c.path for c in self.chars], signature="o"
                ),
            }

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv")
        def Set(self, iface, prop, value):
            pass

    class Application(dbus.service.Object):
        def __init__(self, services):
            self.path = "/org/bluez/fakelock"
            self.services = services
            super().__init__(bus, self.path)

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v"
        )
        def Get(self, iface, prop):
            return self.GetAll(iface)[prop]

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}"
        )
        def GetAll(self, iface):
            return {
                "Services": dbus.Array([s.path for s in self.services], signature="o")
            }

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ssv")
        def Set(self, iface, prop, value):
            pass

        @dbus.service.method(
            "org.freedesktop.DBus.ObjectManager", out_signature="a{oa{sa{sv}}}"
        )
        def GetManagedObjects(self):

            out = dbus.Dictionary({}, signature="oa{sa{sv}}")
            for svc in self.services:
                out[dbus.ObjectPath(svc.path)] = dbus.Dictionary(
                    {
                        "org.bluez.GattService1": dbus.Dictionary(
                            {
                                "UUID": dbus.String(svc.uuid),
                                "Primary": dbus.Boolean(svc.primary),
                                "Characteristics": dbus.Array(
                                    [dbus.ObjectPath(c.path) for c in svc.chars],
                                    signature="o",
                                ),
                            },
                            signature="sv",
                        ),
                    },
                    signature="sa{sv}",
                )
                for ch in svc.chars:
                    out[dbus.ObjectPath(ch.path)] = dbus.Dictionary(
                        {
                            "org.bluez.GattCharacteristic1": dbus.Dictionary(
                                {
                                    "UUID": dbus.String(ch.uuid),
                                    "Service": dbus.ObjectPath(ch.service_path),
                                    "Flags": dbus.Array(ch.flags, signature="s"),
                                },
                                signature="sv",
                            ),
                        },
                        signature="sa{sv}",
                    )
            return out

    class Advertisement(dbus.service.Object):
        def __init__(self, index, local_name, uuids):
            self.path = f"/org/bluez/fakelock/advertisement{index}"
            self.local_name = local_name
            self.uuids = uuids
            super().__init__(bus, self.path)

        def props(self):
            return {
                "Type": "peripheral",
                "ServiceUUIDs": dbus.Array(self.uuids, signature="s"),
                "LocalName": dbus.String(self.local_name),
            }

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v"
        )
        def Get(self, iface, prop):
            return self.props()[prop]

        @dbus.service.method(
            "org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}"
        )
        def GetAll(self, iface):
            return dbus.Dictionary(self.props(), signature="sv")

        @dbus.service.method("org.bluez.LEAdvertisement1")
        def Release(self):
            print("[adv] released")

    write_char = Characteristic(0, WRITE_UUID, ["write", "write-without-response"], 0)

    notify_char = Characteristic(1, NOTIFY_UUID, ["read", "notify"], 0)
    service = Service(0, SVC_UUID, True, [write_char, notify_char])
    app = Application([service])
    adv = Advertisement(0, name, [SVC_UUID])

    def send_notification(payload):
        print(
            f"[notify] skickar {len(payload)} byte: {payload.hex()}"
            f"  (prenumererar: {notify_char.notifying})"
        )
        notify_char.value = array.array("B", payload)
        notify_char.PropertiesChanged(
            "org.bluez.GattCharacteristic1",
            {"Value": dbus.Array(payload, signature="y")},
            [],
        )

    notify_holder["send"] = send_notification
    print("[1] GATT-objekt skapade")

    if selftest_only:
        import re as _re

        root = bus.get_object(bus.get_unique_name(), app.path)
        intro = root.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable")
        print(
            "[selftest] gränssnitt pa appobjektet:",
            sorted(set(_re.findall(r"interface name=\"([^\"]+)\"", intro))),
        )
        objs = dbus.Interface(
            root, "org.freedesktop.DBus.ObjectManager"
        ).GetManagedObjects()
        print(f"[selftest] GetManagedObjects gav {len(objs)} objekt")
        for k in objs:
            print("   ", k, list(objs[k].keys()))
        return

    props = dbus.Interface(
        bus.get_object(BLUEZ, adapter_path), "org.freedesktop.DBus.Properties"
    )
    try:
        if not props.Get(ADAPTER_IFACE, "Powered"):
            props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
    except dbus.exceptions.DBusException as e:
        print(f"(kunde inte satta Powered: {e.get_dbus_name()} - fortsatter anda)")

    root_obj = bus.get_object(BLUEZ, "/org/bluez")
    intro = root_obj.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable")
    import re as _re

    found = _re.findall(r'node name="(hci\d+)"', intro)
    if adapter not in found:
        print(
            f"Adaptern {adapter!r} finns inte. Tillgangliga: {', '.join(found) or 'inga'}"
        )
        print("Kolla med: bluetoothctl list")
        return

    print("[2] registrerar GATT-applikation och annons (asynkront)...")
    gatt_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), GATT_MANAGER)
    adv_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), ADV_MANAGER)

    for mgr, fn, path in (
        (adv_mgr, "UnregisterAdvertisement", adv.path),
        (gatt_mgr, "UnregisterApplication", app.path),
    ):
        try:
            getattr(mgr, fn)(path)
        except dbus.exceptions.DBusException:
            pass

    def gatt_ok():
        print("[3] GATT-applikation registrerad")

    def gatt_fail(err):
        print(f"RegisterApplication misslyckades: {err.get_dbus_name()}")
        print("Kor: sudo systemctl restart bluetooth   och forsok igen")

    def adv_ok():
        print(f"[4] annonserar som {name!r} pa {adapter}")

    def adv_fail(err):
        print(f"RegisterAdvertisement misslyckades: {err.get_dbus_name()}")

    gatt_mgr.RegisterApplication(
        app.path,
        dbus.Dictionary({}, signature="sv"),
        reply_handler=gatt_ok,
        error_handler=gatt_fail,
    )
    adv_mgr.RegisterAdvertisement(
        adv.path,
        dbus.Dictionary({}, signature="sv"),
        reply_handler=adv_ok,
        error_handler=adv_fail,
    )

    print(
        f"Forvantad deviceKey: {expected_key!r}   sessionsnyckel: 0x{session_key:02X}"
    )
    print("Tryck enheten i appen och se ramarna har. Ctrl-C for att avsluta.")
    GLib.MainLoop().run()


def main():
    ap = argparse.ArgumentParser(description="Emulerat Omni-las over BLE")
    ap.add_argument("--name", default="Scooter1", help="annonserat BLE-namn")
    ap.add_argument("--key", default="4BKNwi77", help="deviceKey appen ska skicka")
    ap.add_argument("--session-key", default="0x5A", help="nyckeln laset svarar med")
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="testa GATT-exporten, ingen registrering",
    )
    ap.add_argument(
        "--log", metavar="FIL", help="skriv ocksa all utskrift till denna fil"
    )
    a = ap.parse_args()
    if a.log:
        _f = open(a.log, "a", buffering=1)
        sys.stdout = _Tee(sys.__stdout__, _f)
        sys.stderr = _Tee(sys.__stderr__, _f)
        print(
            f"--- start {__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S} ---"
        )

    session_key = int(a.session_key, 0) & 0xFF
    try:
        if a.selftest:
            run_peripheral(a.name, a.key, session_key, a.adapter, selftest_only=True)
            return
        run_peripheral(a.name, a.key, session_key, a.adapter)
    except ImportError:
        sys.exit(
            "saknar dbus-python/PyGObject. Paket: python3-dbus python3-gi\n"
            "Kor: sudo python3 fake_lock.py"
        )


if __name__ == "__main__":
    main()
