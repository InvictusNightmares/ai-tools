#!/usr/bin/env python3
"""Low-volume incremental monitor for an official JSON API/feed.

It supports one GET/POST JSON response, dotted item/ID paths, required output
field projection, literal filters, stateful new/changed detection, JSON/CSV
output, and standard-library-only execution. It does not implement provider-
specific pagination, bypass authentication/rate limits, or decide data rights.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="Official JSON endpoint")
    p.add_argument("--method", choices=("GET", "POST"), default="GET")
    p.add_argument("--body-json", help="POST body as JSON string, or @path/to/body.json")
    p.add_argument("--header", action="append", default=[], metavar="NAME:VALUE", help="Repeatable non-secret header only")
    p.add_argument("--header-env", action="append", default=[], metavar="NAME:ENV_VAR", help="Read a secret header value from an environment variable")
    p.add_argument("--header-file", action="append", default=[], metavar="NAME:PATH", help="Read a secret header value from a chmod-600 file")
    p.add_argument("--items-path", default="", help="Dotted path to result array, e.g. data.opportunitiesData")
    p.add_argument("--id-field", required=True, help="Dotted unique-ID field inside each item")
    p.add_argument("--select", action="append", required=True, metavar="OUTPUT_NAME=DOTTED.PATH", help="Required repeatable output-field whitelist")
    p.add_argument("--contains", action="append", default=[], help="Case-insensitive literal; every supplied term must occur in serialized item")
    p.add_argument("--state", default=".feed-alert-state.json")
    p.add_argument("--out", help="Output path; stdout if omitted")
    p.add_argument("--format", choices=("json", "csv"), default="json")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--timeout", type=float, default=20)
    p.add_argument(
        "--user-agent",
        required=True,
        help="Real organization/app plus a monitored contact email or HTTPS URL",
    )
    p.add_argument("--dry-run", action="store_true", help="Fetch and report but do not update state")
    return p.parse_args()


def dotted(value, path: str):
    if not path:
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(path)
    return current


def parse_headers(values: list[str]) -> dict[str, str]:
    headers = {}
    for value in values:
        if ":" not in value:
            raise SystemExit(f"invalid --header {value!r}; expected NAME:VALUE")
        name, content = value.split(":", 1)
        name = name.strip()
        if not name:
            raise SystemExit("header name must not be empty")
        headers[name] = content.strip()
    return headers


def parse_named_sources(values: list[str], kind: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        if ":" not in value:
            raise SystemExit(f"invalid --header-{kind} {value!r}; expected NAME:{'ENV_VAR' if kind == 'env' else 'PATH'}")
        name, source = (part.strip() for part in value.split(":", 1))
        if kind == "env":
            content = os.environ.get(source)
            if content is None:
                raise SystemExit(f"environment variable {source!r} is not set")
        else:
            path = Path(source)
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                raise SystemExit(f"secret file {path} must not be group/world accessible; use chmod 600")
            content = path.read_text(encoding="utf-8").strip()
        headers[name] = content
    return headers


def parse_select(values: list[str]) -> list[tuple[str, str]]:
    selections: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --select {value!r}; expected OUTPUT_NAME=DOTTED.PATH")
        name, path = (part.strip() for part in value.split("=", 1))
        if not name or not path or name in seen:
            raise SystemExit(f"invalid or duplicate --select output name: {name!r}")
        seen.add(name)
        selections.append((name, path))
    return selections


def validate_https_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.casefold() != "https" or not parts.hostname:
        raise SystemExit("--url must be an absolute https:// URL")
    if parts.username is not None or parts.password is not None:
        raise SystemExit("refusing credentials embedded in --url")


def validate_user_agent(value: str) -> str:
    value = value.strip()
    lowered = value.casefold()
    placeholders = ("replace-with", "example.com", "example.invalid", "your-email", "yourdomain")
    if "\r" in value or "\n" in value:
        raise SystemExit("--user-agent must not contain CR/LF")
    if len(value) < 10 or any(marker in lowered for marker in placeholders):
        raise SystemExit("--user-agent must identify a real organization/app and monitored contact")
    if "@" not in value and "https://" not in lowered:
        raise SystemExit("--user-agent must contain a monitored email or HTTPS contact URL")
    return value


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_https_url(newurl)
        validate_https_url(req.full_url)
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        old_origin = (old.hostname.casefold(), old.port or 443)
        new_origin = (new.hostname.casefold(), new.port or 443)
        if old_origin != new_origin:
            raise SystemExit(
                "refusing cross-origin redirect; follow the final HTTPS endpoint explicitly "
                "so credentials cannot be forwarded to another host"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def reject_secret_query(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    sensitive = {"api_key", "api-key", "apikey", "key", "token", "access_token", "access-token", "secret", "password"}
    keys = {key.casefold() for key, _ in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)}
    if keys & sensitive:
        raise SystemExit("refusing credentials in --url query; use --header-env or --header-file")


def request_json(args: argparse.Namespace):
    validate_https_url(args.url)
    reject_secret_query(args.url)
    user_agent = validate_user_agent(args.user_agent)
    literal_headers = parse_headers(args.header)
    secret_headers = {
        **parse_named_sources(args.header_env, "env"),
        **parse_named_sources(args.header_file, "file"),
    }
    all_supplied_headers = {**literal_headers, **secret_headers}
    if "user-agent" in {name.casefold() for name in all_supplied_headers}:
        raise SystemExit("set User-Agent only with the required --user-agent option")
    for name in literal_headers:
        if name.casefold() in {"authorization", "x-api-key", "api-key", "proxy-authorization", "cookie", "set-cookie"}:
            raise SystemExit(f"refusing secret-looking --header {name!r}; use --header-env or --header-file")
    headers = {
        "Accept": "application/json",
        **literal_headers,
        **secret_headers,
        "User-Agent": user_agent,
    }
    body = None
    if args.body_json:
        raw = Path(args.body_json[1:]).read_text(encoding="utf-8") if args.body_json.startswith("@") else args.body_json
        body = json.dumps(json.loads(raw)).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(args.url, data=body, headers=headers, method=args.method)
    opener = urllib.request.build_opener(HTTPSOnlyRedirectHandler())
    try:
        with opener.open(request, timeout=args.timeout) as response:
            validate_https_url(response.geturl())
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise RuntimeError(f"endpoint did not return JSON: {content_type}")
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from endpoint") from exc


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"items": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("items"), dict):
        raise RuntimeError("state file is invalid")
    return data


def spreadsheet_safe_cell(value):
    """Neutralize strings that spreadsheet apps may interpret as formulas."""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        stripped = value.lstrip()
        if value.startswith(("\t", "\r", "\n")) or stripped.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def write_results(results: list[dict], fmt: str, path: str | None, selected_names: list[str]) -> None:
    if fmt == "json":
        payload = json.dumps(results, ensure_ascii=False, indent=2)
        if path:
            Path(path).write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return
    handle = Path(path).open("w", encoding="utf-8-sig", newline="") if path else sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=("change", "id", "sha256", *selected_names))
        writer.writeheader()
        for row in results:
            writer.writerow({key: spreadsheet_safe_cell(value) for key, value in row.items()})
    finally:
        if path:
            handle.close()


def main() -> None:
    args = cli()
    if args.limit < 1 or args.limit > 10_000:
        raise SystemExit("--limit must be 1..10000; keep it far below the provider's limit")
    payload = request_json(args)
    items = dotted(payload, args.items_path)
    if not isinstance(items, list):
        raise RuntimeError("--items-path must resolve to a JSON array")
    terms = [term.casefold() for term in args.contains]
    selections = parse_select(args.select)
    filtered = []
    for item in items:
        text = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if all(term in text.casefold() for term in terms):
            filtered.append(item)
        if len(filtered) >= args.limit:
            break
    state_path = Path(args.state)
    state = load_state(state_path)
    previous = state["items"]
    current = dict(previous)
    results = []
    for item in filtered:
        item_id = str(dotted(item, args.id_field))
        projected = {name: dotted(item, path) for name, path in selections}
        canonical = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        old = previous.get(item_id)
        change = "new" if old is None else "changed" if old != digest else "unchanged"
        current[item_id] = digest
        if change != "unchanged":
            results.append({"change": change, "id": item_id, "sha256": digest, **projected})
    write_results(results, args.format, args.out, [name for name, _ in selections])
    if not args.dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"items": current}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"checked={len(filtered)} changed={len(results)} state_updated={not args.dry_run}", file=sys.stderr)


if __name__ == "__main__":
    main()
