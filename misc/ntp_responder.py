#!/usr/bin/env python3
"""Responds to Aliyun MQTT NTP requests."""

import argparse
import json
import re
import time

import paho.mqtt.client as mqtt

REQ_RE = re.compile(r"^/ext/ntp/([^/]+)/([^/]+)/request$")


def now_ms() -> int:
    return int(time.time() * 1000)


def extract_device_send_time(payload: bytes):

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

    broker = args.broker.replace("mqtt://", "").replace("tcp://", "")
    if broker.startswith("["):
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
        print(
            "[ntp_responder] %s req len=%d -> resp %s"
            % (msg.topic, len(msg.payload), json.dumps(resp))
        )

    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1, client_id="ntp-responder"
        )
    except AttributeError:

        client = mqtt.Client(client_id="ntp-responder")
    if args.username:
        client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            print("[ntp_responder] connecting to %s:%d ..." % (broker, args.port))
            client.connect(broker, args.port, 60)
            break
        except OSError as e:
            print(
                "[ntp_responder] cannot reach %s:%d (%s) -"
                " retrying in 5 s. Ctrl-C to cancel." % (broker, args.port, e)
            )
            time.sleep(5)
    client.loop_forever()


if __name__ == "__main__":
    main()
