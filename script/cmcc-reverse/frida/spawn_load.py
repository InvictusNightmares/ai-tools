#!/usr/bin/env python3
"""Spawn an Android package with Frida, load a script, and keep the session alive.

Examples:
  python3 spawn_load.py --device emulator-5554 --package com.example.app --script hook.js
  python3 spawn_load.py --host 127.0.0.1:27042 --package com.example.app --script hook.js --wait-ready
"""
from __future__ import annotations

import argparse
import threading
import time

import frida


def get_device(args):
    if args.host:
        return frida.get_device_manager().add_remote_device(args.host)
    if args.device:
        return frida.get_device(args.device, timeout=10)
    return frida.get_usb_device(timeout=10)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", help="Frida device id, e.g. emulator-5554")
    ap.add_argument("--host", help="remote frida-server, e.g. 127.0.0.1:27042")
    ap.add_argument("--package", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--wait-ready", action="store_true", help="wait for send({type:'java-ready'})")
    ap.add_argument("--ready-timeout", type=float, default=8.0)
    ap.add_argument("--keep", action="store_true", help="keep process alive after loading")
    args = ap.parse_args()

    source = open(args.script, encoding="utf-8").read()
    dev = get_device(args)
    print(f"[runner] device: {dev}", flush=True)

    pid = dev.spawn([args.package])
    print(f"[runner] spawned pid={pid}", flush=True)

    session = dev.attach(pid)
    script = session.create_script(source)
    ready = threading.Event()

    def on_message(message, data):
        print(f"[frida] {message}", flush=True)
        try:
            payload = message.get("payload") or {}
            if message.get("type") == "send" and payload.get("type") == "java-ready":
                ready.set()
        except Exception:
            pass

    script.on("message", on_message)
    script.on("destroyed", lambda: print("[runner] script destroyed", flush=True))
    script.load()
    print("[runner] script loaded", flush=True)

    if args.wait_ready:
        if ready.wait(args.ready_timeout):
            print("[runner] java-ready", flush=True)
        else:
            print("[runner] java-ready timeout; resuming anyway", flush=True)

    dev.resume(pid)
    print(f"[runner] resumed pid={pid}", flush=True)

    if args.keep:
        try:
            while True:
                time.sleep(2)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
