#!/usr/bin/env python3
"""Auto-responder for Aliyun /ext/ntp requests (lokal broker-emulering).

Subscribar pa /ext/ntp/<pk>/<dn>/request och svarar omedelbart pa
motsvarande /response med JSON enligt Aliyuns NTP-spec:
    {"deviceSendTime": <eko>, "serverRecvTime": <nu ms>, "serverSendTime": <nu ms>}

Enheten raknar: Time = (serverRecvTime + serverSendTime + deviceRecvTime
                        - deviceSendTime) / 2

OBS:
- Payloaden i var capture var 8 byte binart, inte JSON. Om enheten fortsatter
  retry:a efter vara JSON-svar betyder det att WITTENSTEIN-firmwaren har egen
  binar inramning - fanga da ett riktigt moln-svar och efterlikna det istallet.
- Faller tillbaka pa att svara med tomma JSON-stamplar korrekt satts anda;
  deviceSendTime ekas bara nar det gar att parsa ur binar/JSON.

Kor:  python3 ntp_responder.py --broker 127.0.0.1[:1883]

BROKERN: Skriptet ar bara "motparten" - det PRATAR MQTT men ar inte sjalv
servern. Det behover en MQTT-broker att ansluta till (det som enheten/din
riktiga klient ocksa publicerar pa). Vanligaste valet ar mosquitto:

  Den har maskinen:  mosquitto -p 1883              (finns pa /usr/sbin/mosquitto)
                     eller som tjanst: systemctl start mosquitto
  Termux (telefon):  pkg install mosquitto && mosquitto -p 1883

Utan igang-kord broker ger paho ett socket-fel ("Connection refused",
gaierror). Starta forst brokern, sen detta skript, sen enheten - da ser du
varje /ext/ntp/--request och svaret som skickas tillbaka.

Termux: pkg install python && pip install paho-mqtt
"""
import argparse
import json
import re
import time

import paho.mqtt.client as mqtt

REQ_RE = re.compile(r"^/ext/ntp/([^/]+)/([^/]+)/request$")


def now_ms() -> int:
    return int(time.time() * 1000)


def extract_device_send_time(payload: bytes):
    """Forsok plocka deviceSendTime ur JSON; binar payload: skicka tillbaka
    enheten kanner igen sin egen tid oavsett - vi ekar bara om JSON."""
    try:
        obj = json.loads(payload.decode("utf-8"))
        return obj.get("deviceSendTime")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--username", default=None)
    ap.add_argument("--password", default=None)
    args = ap.parse_args()

    # --broker far vara "host", "host:port" eller "mqtt://host:port".
    # (Tidigare gick "host:port" rakt in i connect() -> socket.gaierror,
    # vilket sag ut som att skriptet "fragade efter socket".)
    broker = args.broker.replace("mqtt://", "").replace("tcp://", "")
    if broker.startswith("["):          # [ipv6] ev. :port
        broker, _, tail = broker[1:].partition("]")
        if tail.startswith(":") and tail[1:].isdigit():
            args.port = int(tail[1:])
    elif ":" in broker:
        b, p = broker.rsplit(":", 1)
        if p.isdigit():
            broker, args.port = b, int(p)

    def on_connect(client, userdata, flags, rc):
        print("[ntp_responder] connected rc=%d" % rc)
        client.subscribe("/ext/ntp/+/+/request", qos=0)

    def on_message(client, userdata, msg):
        m = REQ_RE.match(msg.topic)
        if not m:
            return
        pk, dn = m.group(1), m.group(2)
        recv = now_ms()
        dst = extract_device_send_time(msg.payload) or recv
        resp = {
            "deviceSendTime": str(dst),
            "serverRecvTime": str(recv),
            "serverSendTime": str(now_ms() + 1),
        }
        topic = "/ext/ntp/%s/%s/response" % (pk, dn)
        client.publish(topic, json.dumps(resp), qos=0)
        print("[ntp_responder] %s req len=%d -> resp %s"
              % (msg.topic, len(msg.payload), json.dumps(resp)))

    # paho-mqtt >=2.0 kraver explicit callback-API-version for klassiska signaturer
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1,
                             client_id="ntp-responder")
    except AttributeError:
        # paho-mqtt 1.x
        client = mqtt.Client(client_id="ntp-responder")
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_message = on_message

    # Tydligt fel + retry i stallet for en socket-traceback nar brokern
    # inte gar att na (eller inte ar igang).
    while True:
        try:
            print("[ntp_responder] ansluter till %s:%d ..." % (broker, args.port))
            client.connect(broker, args.port, 60)
            break
        except OSError as e:
            print("[ntp_responder] kan inte na %s:%d (%s) -"
                  " provar igen om 5 s. Ctrl-C avbryter." % (broker, args.port, e))
            time.sleep(5)
    client.loop_forever()


if __name__ == "__main__":
    main()
