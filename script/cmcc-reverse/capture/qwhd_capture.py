#!/usr/bin/env python3
"""Capture China Mobile and SF Express membership login/activity/ticket flows.

Run:
  export CMCC_CAPTURE_DIR="$PWD/out/captures"
  mitmweb --listen-port 8080 --web-port 8081 \
    --set connection_strategy=lazy \
    --scripts capture/qwhd_capture.py

Outputs (contain secrets; never commit):
  $CMCC_CAPTURE_DIR/qwhd_long.log
  $CMCC_CAPTURE_DIR/qwhd_token.txt
  $CMCC_CAPTURE_DIR/qwhd_apptoken_body.json
  $CMCC_CAPTURE_DIR/qwhd_apptoken_resp.json
  $CMCC_CAPTURE_DIR/flows/<flow-id>.json  # complete paired headers and bodies
  $CMCC_CAPTURE_DIR/sf/flows/<flow-id>.json  # SF membership flows, kept separate
  $CMCC_CAPTURE_DIR/sf/sf.log

This addon runs after TLS decryption. It cannot make an app trust the proxy CA
or bypass certificate pinning. Capturing a login does not prove it is renewable.
"""
from __future__ import annotations

import base64
import datetime
import ipaddress
import json
import os
import pathlib
import re
import tempfile
from urllib.parse import urlsplit

from OpenSSL import SSL

from mitmproxy import connection, ctx, http, tls
from mitmproxy.addons.tlsconfig import TlsConfig
from mitmproxy.net import tls as net_tls

OUT = pathlib.Path(os.environ.get("CMCC_CAPTURE_DIR", "out/captures"))
OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
FLOWS = OUT / "flows"
FLOWS.mkdir(exist_ok=True, mode=0o700)
SF_OUT = OUT / "sf"
SF_OUT.mkdir(exist_ok=True, mode=0o700)
SF_FLOWS = SF_OUT / "flows"
SF_FLOWS.mkdir(exist_ok=True, mode=0o700)
SF_LOG = SF_OUT / "sf.log"

LOG = OUT / "qwhd_long.log"
TOKEN = OUT / "qwhd_token.txt"
APPTOKEN_BODY = OUT / "qwhd_apptoken_body.json"
APPTOKEN_RESP = OUT / "qwhd_apptoken_resp.json"

PAT = re.compile(r"(?:^|;\s*)QWHD_SESSION_TOKEN=([^;]+)")
NATIVE_HOSTS = {"client.app.coc.10086.cn", "clientaccess.10086.cn"}
SF_MEMBERSHIP_HOST = "mcs-mimp-web.sf-express.com"
SF_CAPTURE_KINDS = {"sf-membership", "sf-native-ticket"}
SF_TICKET_PATH = "/cx-app-member/member/app/user/universalSign"
# This upstream does not advertise RFC 5746 support. Scope compatibility to
# this endpoint and SSL connection; never modify a cached SSL.Context.
LEGACY_TLS_HOSTS = {"client.app.coc.10086.cn"}


def tls_start_server(data: tls.TlsData) -> None:
    server = data.conn
    if data.is_dtls or not isinstance(server, connection.Server) or not server.address:
        return
    host, port = server.address
    host = host.lower().rstrip(".")
    if host not in LEGACY_TLS_HOSTS or port != 443:
        return
    sni = server.sni or data.context.client.sni or host
    if sni.lower().rstrip(".") != host:
        return
    if data.ssl_conn is None:
        # Script hooks run before the built-in TlsConfig addon. Reuse its
        # normal CA, hostname, TLS version and cipher configuration; the
        # built-in hook will subsequently see ssl_conn and leave it intact.
        TlsConfig().tls_start_server(data)
    if data.ssl_conn is not None:
        data.ssl_conn.set_options(net_tls.OP_LEGACY_SERVER_CONNECT | SSL.OP_NO_RENEGOTIATION)


def is_sf_host(host: str) -> bool:
    return host in {"sf-express.com", "sf-express.com.cn"} or host.endswith(
        (".sf-express.com", ".sf-express.com.cn")
    )


def capture_host(flow: http.HTTPFlow) -> str:
    host = flow.request.host.lower().rstrip(".")
    if flow.client_conn.proxy_mode.type_name != "wireguard":
        return host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    # WireGuard keeps the destination IP, including fake-IP DNS addresses.
    # Recover only SF origins with matching HTTP authority and TLS SNI.
    sni = (flow.client_conn.sni or "").lower().rstrip(".")
    authority = flow.request.pretty_host.lower().rstrip(".")
    return sni if is_sf_host(sni) and authority == sni else host


def capture_kind(flow: http.HTTPFlow) -> str | None:
    host = capture_host(flow)
    path = urlsplit(flow.request.url).path
    if is_sf_host(host) and path.endswith(SF_TICKET_PATH):
        return "sf-native-ticket"
    if host == SF_MEMBERSHIP_HOST and (
        path.startswith(("/mcs-mimp/", "/share/", "/superWelfare/"))
        or path in {"/mcs-mimp", "/superWelfare"}
    ):
        return "sf-membership"
    if host == "wx.10086.cn":
        if path in ("/qwhdsso/appTokenLogin", "/qwhdsso/jwtLogin"):
            return "app-token-login"
        if path.startswith(("/qwhdhub/", "/qwhdsso/")):
            return "qwhd-activity"
    if host == "wap.js.10086.cn":
        if path.startswith("/nact/"):
            return "jiangsu-activity"
        if path in {
            "/vw/gateway/auth/auth/jtWx10086AuthLogin",
            "/hyl/content/provider-user/sso/china/mobile",
        }:
            return "jiangsu-sso"
    if host in NATIVE_HOSTS and "/uamonekeylogin/" in path:
        return "native-auto-login" if path.endswith("/autoLogin") else "native-login"
    if host in NATIVE_HOSTS and path.startswith("/biz-orange/"):
        return "native-api"
    return None


def write_private(path: pathlib.Path, text: str) -> None:
    # NamedTemporaryFile creates a 0600 file; replace atomically and never follow
    # an existing destination symlink. This also tightens older 0644 outputs.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".capture-", delete=False
        ) as fh:
            temporary = pathlib.Path(fh.name)
            fh.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def log(msg: str, kind: str | None = None) -> None:
    path = SF_LOG if kind in SF_CAPTURE_KINDS else LOG
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        os.fchmod(fh.fileno(), 0o600)
        fh.write(msg + "\n")


def save_token(token: str, where: str) -> None:
    write_private(TOKEN, token + "\n")
    print(f"[TOKEN] saved len={len(token)} from={where}", flush=True)


def message_data(message: http.Message) -> dict:
    try:
        text = message.get_text(strict=False)
    except ValueError:
        text = None
    return {
        "http_version": message.http_version,
        "headers": list(message.headers.items(multi=True)),
        "body_base64": base64.b64encode(message.raw_content or b"").decode("ascii"),
        "body_available": message.raw_content is not None,
        "text": text,
    }


def flow_path(flow: http.HTTPFlow, kind: str) -> pathlib.Path:
    directory = SF_FLOWS if kind in SF_CAPTURE_KINDS else FLOWS
    return directory / f"{flow.id}.json"


def save_flow(flow: http.HTTPFlow, kind: str) -> None:
    record = {
        "id": flow.id,
        "kind": kind,
        "transport": flow.client_conn.proxy_mode.type_name,
        "started_at": flow.request.timestamp_start,
        "request": {
            "method": flow.request.method,
            "url": flow.request.url,
            "origin_host": capture_host(flow),
            **message_data(flow.request),
        },
        "response": None,
        "error": flow.error.msg if flow.error else None,
    }
    if flow.response is not None:
        record["response"] = {"status_code": flow.response.status_code, **message_data(flow.response)}
    write_private(flow_path(flow, kind), json.dumps(record, ensure_ascii=False, indent=2))
    status = flow.response.status_code if flow.response is not None else "pending"
    print(f"[capture] {kind} {flow.request.method} status={status} id={flow.id}", flush=True)


def running() -> None:
    # A script reload can recover matching traffic already retained by mitmweb.
    # Read the store only: do not replay requests or overwrite existing evidence.
    view = getattr(getattr(ctx, "master", None), "view", None)
    if view is None:
        return
    recovered = 0
    inventory: dict[str, dict] = {}
    for flow in view.resolve("@all"):
        if not isinstance(flow, http.HTTPFlow):
            continue
        host = capture_host(flow)
        entry = inventory.setdefault(host, {"flows": 0, "statuses": {}, "errors": 0})
        entry["flows"] += 1
        status = str(flow.response.status_code) if flow.response else "pending"
        entry["statuses"][status] = entry["statuses"].get(status, 0) + 1
        entry["errors"] += bool(flow.error)
        sf_host = is_sf_host(host)
        if host == "wap.js.10086.cn" or sf_host:
            # Diagnose activity routing changes without retaining query values
            # or bodies from endpoints outside the current capture filter.
            path = urlsplit(flow.request.url).path
            if sf_host:
                path = re.sub(
                    r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}",
                    "<opaque>", path,
                )
                path = re.sub(r"[0-9a-fA-F]{32}", "<opaque>", path)
            path = re.sub(r"\d{7,}", "<number>", path)
            path = re.sub(r"[A-Za-z0-9_-]{40,}", "<opaque>", path)
            paths = entry.setdefault("paths", {})
            paths[path] = paths.get(path, 0) + 1
        kind = capture_kind(flow)
        if kind is not None and not flow_path(flow, kind).exists():
            save_flow(flow, kind)
            recovered += 1
    # Discover an omitted authentication host without persisting unrelated URLs,
    # headers, bodies, or credentials from the rest of the phone's traffic.
    write_private(OUT / "host_inventory.json", json.dumps({"hosts": inventory}, indent=2))
    print(f"[capture] recovered retained flows={recovered}", flush=True)


def request(flow: http.HTTPFlow) -> None:
    kind = capture_kind(flow)
    if kind is None:
        return

    save_flow(flow, kind)
    log(f"{datetime.datetime.now()} REQ {flow.request.method} {flow.request.url}", kind)

    cookie = "; ".join(flow.request.headers.get_all("cookie"))
    if cookie and kind in ("qwhd-activity", "app-token-login"):
        match = PAT.search(cookie)
        if match:
            save_token(match.group(1), "request-cookie")

    for key in ("user-agent", "referer", "origin", "x-requested-with", "cookie"):
        value = flow.request.headers.get(key)
        if value:
            log(f"H {key}: {value[:1500]}", kind)

    try:
        body = flow.request.get_text(strict=False)
    except Exception:
        body = ""
    if body:
        log("BODY: " + body[:2000], kind)

    if kind == "app-token-login":
        write_private(APPTOKEN_BODY, body or "")
        log("APPTOKEN_BODY_SAVED", kind)


def response(flow: http.HTTPFlow) -> None:
    kind = capture_kind(flow)
    if kind is None or flow.response is None:
        return

    save_flow(flow, kind)
    log(f"RESP {flow.response.status_code} {flow.request.url}", kind)

    for cookie in flow.response.headers.get_all("set-cookie"):
        match = PAT.search(cookie)
        if match and kind in ("qwhd-activity", "app-token-login"):
            save_token(match.group(1), "set-cookie")
        if "QWHD" in cookie or "jwt" in cookie.lower():
            log("SET-COOKIE: " + cookie[:800], kind)

    try:
        text = flow.response.get_text(strict=False)
    except Exception:
        text = ""
    if text:
        log("RESP_BODY: " + text[:2000], kind)

    if kind == "app-token-login":
        write_private(APPTOKEN_RESP, text or "")
        log("APPTOKEN_RESP_SAVED", kind)


def error(flow: http.HTTPFlow) -> None:
    kind = capture_kind(flow)
    if kind is not None:
        save_flow(flow, kind)
