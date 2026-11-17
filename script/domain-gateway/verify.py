#!/usr/bin/env python3
"""Check trusted HTTPS without following redirects or printing private URLs."""

import argparse
import hashlib
import http.client
import json
import ssl
import sys
from urllib.parse import urlsplit

from common import ConfigError, load_private, text


def check(entry, context=None):
    if not isinstance(entry, dict):
        raise ConfigError("each check must be an object")
    label = text(entry.get("label"), "label")
    if not all(c.isalnum() or c in "_-" for c in label):
        raise ConfigError("use a generic identifier for each check label")
    url = urlsplit(text(entry.get("url"), "url"))
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
        raise ConfigError("checks require HTTPS URLs without embedded credentials or fragments")
    expected = entry.get("status")
    if type(expected) is not int or not 100 <= expected <= 599:
        raise ConfigError("expected HTTP status is required")
    connection = http.client.HTTPSConnection(url.hostname, url.port, timeout=15, context=context or ssl.create_default_context())
    try:
        connection.connect()
        certificate = connection.sock.getpeercert()
        connection.request("GET", (url.path or "/") + ("?" + url.query if url.query else ""))
        response = connection.getresponse()
        digest = hashlib.sha256()
        size = 0
        while chunk := response.read(65536):
            size += len(chunk)
            if size > 16 * 1024 * 1024:
                raise ValueError("response exceeds verification limit")
            digest.update(chunk)
        ok = response.status == expected
        if entry.get("sha256"):
            ok = ok and digest.hexdigest() == entry["sha256"]
        return {"label": label, "ok": ok, "status": response.status, "trusted_tls": True, "expires": certificate.get("notAfter")}
    except (OSError, ValueError, http.client.HTTPException) as error:
        return {"label": label, "ok": False, "error": type(error).__name__}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        entries = load_private(args.config).get("checks")
        if not isinstance(entries, list) or not entries:
            raise ConfigError("checks must be a nonempty list")
        results = [check(entry) for entry in entries]
    except (ConfigError, OSError, ValueError, TypeError):
        print("invalid private verification configuration", file=sys.stderr)
        return 1
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
