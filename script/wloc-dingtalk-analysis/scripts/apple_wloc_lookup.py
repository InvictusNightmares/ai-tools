#!/usr/bin/env python3
"""Query Apple's WLOC service for a BSSID and list nearby known APs.

Apple's gs-loc /clls/wloc endpoint is undocumented and uses a reverse-engineered
protobuf protocol. This is a local research tool; use it only for your own APs
or equipment you are authorized to test.

Usage:
    python3 apple_wloc_lookup.py AA:BB:CC:DD:EE:FF
    python3 apple_wloc_lookup.py AA:BB:CC:DD:EE:FF --near 20
    python3 apple_wloc_lookup.py AA:BB:CC:DD:EE:FF --radius 50 --json

The response contains the queried BSSID plus many nearby BSSIDs that Apple knows.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import urllib.error
import urllib.request

USER_AGENT = "locationd/1753.17 CFNetwork/889.9 Darwin/17.2.0"
HOSTS = ("gs-loc.apple.com", "gs-loc-cn.apple.com")
APPLE_UNKNOWN = -18000000000


# --- minimal protobuf ------------------------------------------------------

def encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        seven = value & 0x7F
        value >>= 7
        out.append(seven | (0x80 if value else 0))
        if not value:
            return bytes(out)


def read_varint(buf: bytes, offset: int):
    result = shift = 0
    while True:
        byte = buf[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, offset
        shift += 7


def tag(field: int, wire: int) -> bytes:
    return encode_varint((field << 3) | wire)


def ld(field: int, data: bytes) -> bytes:
    return tag(field, 2) + encode_varint(len(data)) + data


def as_signed_64(value: int) -> int:
    return value - (1 << 64) if value >= (1 << 63) else value


def build_request(bssids):
    devices = b"".join(ld(2, ld(1, b.encode())) for b in bssids)
    payload = devices + tag(3, 0) + encode_varint(0) + tag(4, 0) + encode_varint(0)
    frame = (b"\x00\x01\x00\x05en_US"
             b"\x00\x13com.apple.locationd"
             b"\x00\x0a8.1.12B411"
             b"\x00\x00\x00\x01\x00\x00")
    return frame + struct.pack(">H", len(payload)) + payload


# --- response parsing ------------------------------------------------------

def parse_location(buf):
    lat = lon = None
    offset, end = 0, len(buf)
    while offset < end:
        key, offset = read_varint(buf, offset)
        field, wire = key >> 3, key & 0x7
        if wire == 0:
            value = as_signed_64(read_varint(buf, offset)[0])
            offset = read_varint(buf, offset)[1]
            if field == 1:
                lat = value
            elif field == 2:
                lon = value
        elif wire == 2:
            length, offset = read_varint(buf, offset)
            offset += length
        else:
            break
    if lat is None or lon is None or lat == APPLE_UNKNOWN or lon == APPLE_UNKNOWN:
        return None
    return lat * 1e-8, lon * 1e-8


def parse_wifi_device(buf):
    bssid = coords = None
    offset, end = 0, len(buf)
    while offset < end:
        key, offset = read_varint(buf, offset)
        field, wire = key >> 3, key & 0x7
        if wire == 2:
            length, offset = read_varint(buf, offset)
            chunk = buf[offset:offset + length]
            offset += length
            if field == 1:
                bssid = chunk.decode(errors="replace")
            elif field == 2:
                coords = parse_location(chunk)
        elif wire == 0:
            offset = read_varint(buf, offset)[1]
        else:
            break
    return bssid, coords


def normalize_bssid(bssid: str) -> str:
    return ":".join(o.rjust(2, "0").lower() for o in bssid.split(":"))


def parse_response(raw: bytes):
    buf = raw[10:]
    located = {}
    offset, end = 0, len(buf)
    while offset < end:
        key, offset = read_varint(buf, offset)
        field, wire = key >> 3, key & 0x7
        if wire == 2:
            length, offset = read_varint(buf, offset)
            chunk = buf[offset:offset + length]
            offset += length
            if field == 2:
                bssid, coords = parse_wifi_device(chunk)
                if bssid and coords:
                    located[normalize_bssid(bssid)] = coords
        elif wire == 0:
            offset = read_varint(buf, offset)[1]
        else:
            break
    return located


def query(host: str, bssids):
    req = urllib.request.Request(
        f"https://{host}/clls/wloc",
        data=build_request(bssids),
        headers={"User-Agent": USER_AGENT,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


# --- helpers ---------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bssid", help="AA:BB:CC:DD:EE:FF")
    parser.add_argument("--near", type=int, default=10,
                        help="how many nearby BSSIDs to print (default 10)")
    parser.add_argument("--radius", type=float, default=100.0,
                        help="nearby radius in meters (default 100)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    target = normalize_bssid(args.bssid)
    last_error = None
    located = None
    used_host = None
    for host in HOSTS:
        try:
            located = parse_response(query(host, [target]))
            used_host = host
            break
        except Exception as error:  # noqa: BLE001
            last_error = error
    if located is None:
        print(f"query failed: {last_error}", file=sys.stderr)
        return 1
    if target not in located:
        print(f"{target} not found in Apple WLOC response", file=sys.stderr)
        return 2

    lat0, lon0 = located[target]
    rows = []
    for bssid, (lat, lon) in located.items():
        if bssid == target:
            continue
        distance = haversine(lat0, lon0, lat, lon)
        if distance <= args.radius:
            rows.append((distance, bssid, lat, lon))
    rows.sort()

    if args.json:
        print(json.dumps({
            "host": used_host,
            "target": target,
            "lat": lat0,
            "lon": lon0,
            "nearby": [
                {"distance_m": round(d, 1), "bssid": b, "lat": la, "lon": lo}
                for d, b, la, lo in rows[:args.near]
            ],
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"host   : {used_host}")
    print(f"target : {target}")
    print(f"lat/lon: {lat0:.8f}, {lon0:.8f}")
    print(f"nearby : {len(rows)} APs within {args.radius:g}m")
    for distance, bssid, lat, lon in rows[:args.near]:
        print(f"  {distance:7.1f}m  {bssid}  {lat:.8f},{lon:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
