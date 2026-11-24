#!/usr/bin/env python3

"""Lokal HTTP-stub för BleTools API med request-loggning."""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import patch_offline

    patch_offline.build_config()
    LOGIN_BEAN = json.loads(patch_offline.PAYLOAD)
except Exception as e:
    print("kunde inte lasa patch_offline.py (%s) - login ger tom data" % e)
    LOGIN_BEAN = {
        "token": "",
        "expiredTimeStamp": 4102444800000,
        "user": {"id": 1, "nickname": "", "role": 5, "lang": "sv"},
        "customerConfig": [],
        "lockFile": [],
        "qrFile": [],
    }

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omni_users.json")
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omni_captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)


def load_users():
    try:
        return json.load(open(USERS_FILE))
    except Exception:
        return {}


def save_users(u):
    json.dump(u, open(USERS_FILE, "w"), indent=1)


def login_response(qs):

    account = (qs.get("account") or [""])[0]
    pwd_md5 = (qs.get("password") or [""])[0]
    if not account or not pwd_md5:
        return {"code": 202, "data": None}
    users = load_users()
    if account not in users:
        users[account] = pwd_md5
        save_users(users)
        print("    NYTT KONTO skapat for", repr(account))
    elif users[account] != pwd_md5:
        print("    FEL losenord for", repr(account))
        return {"code": 202, "data": None}
    data = dict(LOGIN_BEAN)
    data["token"] = "srv-%s" % account
    data["expiredTimeStamp"] = 4102444800000
    return {"code": 200, "data": data}


def canned(path, qs):

    if path.rstrip("/").endswith("login"):
        return login_response(qs)
    if "version/android" in path:
        return {
            "code": 200,
            "data": {
                "content": "",
                "required": 0,
                "url": "",
                "versionCode": "1",
                "versionName": "0.0.1",
            },
        }
    if "oss_key" in path:
        return {"code": 200, "data": {"AliOSSKeyID": "", "AliOSSKeySecret": ""}}

    return {"code": 200, "data": {}}


class QuietServer(ThreadingHTTPServer):

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _handle(self):
        ln = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(ln) if ln else b""
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        print(f"[{self.log_date_time_string()}] {self.command} {u.path}")
        for k, v in qs.items():
            print(f"    ? {k} = {v[0]!r}")
        if body:
            print(f"    body: {body[:500]!r}")

        import time as _t

        ts = _t.strftime("%Y%m%d_%H%M%S") + ("_%03d" % (_t.time() % 1 * 1000))
        safe = "".join(c if c.isalnum() else "_" for c in u.path)[:60] or "root"
        with open(
            os.path.join(CAPTURE_DIR, f"{ts}_{self.command}_{safe}.txt"), "wb"
        ) as fh:
            fh.write(f"{self.command} {self.path}\n".encode())
            for k, v in self.headers.items():
                fh.write(f"{k}: {v}\n".encode())
            fh.write(b"\n")
            fh.write(body)
        payload = json.dumps(canned(u.path, qs)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        print(f"    -> {payload.decode()[:160]}")

    do_GET = do_POST = do_PUT = _handle

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18080)
    args = ap.parse_args()
    srv = QuietServer((args.host, args.port), Handler)
    print(f"lyssnar pa http://{args.host}:{args.port}/  (Ctrl-C stannar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
