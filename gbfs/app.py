#!/usr/bin/env python3
"""Small local GBFS scooter browser for Linux."""

from __future__ import annotations

import json
import mimetypes
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
GBFS_URL = "https://gbfs.api.ridedott.com/public/v2/gbfs.json"
USER_AGENT = "GBFS-Scooter-Browser/0.1 (local Linux app)"


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def get_map_key() -> str:
    """Load the Qick Google Maps key from the provided key file."""
    content = (ROOT / "map_keys.txt").read_text(encoding="utf-8")
    match = re.search(r"Qick[^\n]*\n\s*(AIza[\w-]+)", content)
    if not match:
        raise FileNotFoundError("Hittar inte Qick:s Google Maps-nyckel i map_keys.txt")
    return match.group(1)


def feed_list(document: dict) -> list[dict]:
    """Read both GBFS v2 and v3 discovery document layouts."""
    data = document.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("feeds"), list):
        return data["feeds"]
    if isinstance(data, dict):
        feeds = []
        for locale_data in data.values():
            if isinstance(locale_data, dict):
                feeds.extend(locale_data.get("feeds", []))
        return feeds
    return []


def find_feed(feeds: list[dict], *names: str) -> str | None:
    for name in names:
        for feed in feeds:
            if feed.get("name") == name and feed.get("url"):
                return feed["url"]
    return None


def get_vehicles() -> dict:
    discovery = get_json(GBFS_URL)
    feeds = feed_list(discovery)
    status_url = find_feed(feeds, "vehicle_status", "free_bike_status")
    if not status_url:
        raise ValueError("GBFS-flödet saknar vehicle_status/free_bike_status.")

    status = get_json(status_url)
    data = status.get("data", {})
    vehicles = data.get("vehicles", data.get("bikes", [])) if isinstance(data, dict) else []

    type_url = find_feed(feeds, "vehicle_types")
    types = {}
    if type_url:
        type_data = get_json(type_url).get("data", {})
        for item in type_data.get("vehicle_types", []) if isinstance(type_data, dict) else []:
            types[item.get("vehicle_type_id")] = item

    result = []
    for vehicle in vehicles:
        lat, lon = vehicle.get("lat"), vehicle.get("lon")
        if not isinstance(lat, (float, int)) or not isinstance(lon, (float, int)):
            continue
        vehicle_type = types.get(vehicle.get("vehicle_type_id"), {})
        form_factor = str(vehicle_type.get("form_factor", "")).lower()
        name = str(vehicle_type.get("name", "")).lower()
        # On older feeds without vehicle_types, include available bikes too; the
        # user can still inspect the operator's full free-floating fleet.
        if form_factor and "scooter" not in form_factor and "scooter" not in name:
            continue
        result.append({
            "id": vehicle.get("vehicle_id", "Okänt fordon"),
            "lat": lat,
            "lon": lon,
            "type": vehicle_type.get("name", "Elscooter"),
            "battery": vehicle.get("current_range_meters"),
            "is_reserved": vehicle.get("is_reserved", False),
            "is_disabled": vehicle.get("is_disabled", False),
        })
    return {"vehicles": result, "updated": status.get("last_updated", discovery.get("last_updated"))}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/vehicles":
            try:
                payload = json.dumps(get_vehicles()).encode()
                self.send_response(200)
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
                payload = json.dumps({"error": f"Kunde inte läsa Dott-flödet: {error}"}).encode()
                self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        relative = "index.html" if path == "/" else path.lstrip("/")
        file_path = (STATIC / relative).resolve()
        if STATIC.resolve() not in file_path.parents and file_path != STATIC.resolve():
            self.send_error(404)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        if file_path == STATIC / "index.html":
            content = content.decode("utf-8").replace("__GOOGLE_MAPS_API_KEY__", get_map_key()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    address = ("127.0.0.1", 8811)
    print(f"GBFS Scooter Browser kör på http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, Handler).serve_forever()
