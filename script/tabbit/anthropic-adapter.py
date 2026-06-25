#!/usr/bin/env python3

import html
import json
import os
import random
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


DEFAULT_ENDPOINT = "https://web.tabbit.ai/api/v1/chat/completion"
DEFAULT_MODEL = "Claude-Opus-4.8"
DEFAULT_SESSION_ID = "02eebcbb-57be-4252-b821-eac8cbd1cffc"
DEFAULT_ENTITY_KEY = "d41d8cd98f00b204e9800998ecf8427e"
DEFAULT_REQ_CTX = "MS4xLjM5KDEwMTAxMDM5KQ=="
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
DEFAULT_MODEL_MAP = {
    "claude-opus-4-8": "Claude-Opus-4.8",
    "claude-opus-4.8": "Claude-Opus-4.8",
    "Claude-Opus-4.8": "Claude-Opus-4.8",
    "gemini-3.5-flash": "Gemini-3.5-Flash",
    "Gemini-3.5-Flash": "Gemini-3.5-Flash",
    "glm-5.2": "GLM-5.2",
    "GLM-5.2": "GLM-5.2",
    "deepseek-v4-pro": "DeepSeek-V4-Pro",
    "DeepSeek-V4-Pro": "DeepSeek-V4-Pro",
    "deepseek-v4-flash": "DeepSeek-V4-Flash",
    "DeepSeek-V4-Flash": "DeepSeek-V4-Flash",
    "kimi-k2.6": "Kimi-K2.6",
    "Kimi-K2.6": "Kimi-K2.6",
    "minmax-m3": "MinMax-M3",
    "MinMax-M3": "MinMax-M3",
}

UUID_DEFAULT_BROWSER_MARKER = "1"
UUID_MARKER_POS = 5
UUID_TIMESTAMP_POSITIONS = [2, 7, 11, 14, 18, 21, 25, 28]

request_lock = threading.Lock()


def getenv(name, default=""):
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def read_cookie():
    if os.environ.get("TABBIT_COOKIE"):
        return strip_header_prefix(os.environ["TABBIT_COOKIE"], "Cookie")
    cookie_file = getenv("TABBIT_COOKIE_FILE", "/opt/tabbit/.tabbit-cookie.local")
    with open(cookie_file, "r") as handle:
        return strip_header_prefix(handle.read(), "Cookie")


def strip_header_prefix(value, name):
    trimmed = value.strip()
    prefix = name + ":"
    if trimmed.lower().startswith(prefix.lower()):
        return trimmed[len(prefix) :].strip()
    return trimmed


def tabbit_unique_uuid(is_default_browser=True):
    chars = "0123456789abcdef"
    non_default_chars = chars.replace(UUID_DEFAULT_BROWSER_MARKER, "")
    timestamp_hex = ("%08x" % int(time.time()))[-len(UUID_TIMESTAMP_POSITIONS) :]
    timestamp_by_position = {
        position: timestamp_hex[index] for index, position in enumerate(UUID_TIMESTAMP_POSITIONS)
    }

    raw = []
    for index in range(32):
        if index == UUID_MARKER_POS:
            raw.append(UUID_DEFAULT_BROWSER_MARKER if is_default_browser else random.choice(non_default_chars))
        elif index in timestamp_by_position:
            raw.append(timestamp_by_position[index])
        else:
            raw.append(random.choice(chars))

    raw = "".join(raw)
    return "-".join([raw[:8], raw[8:12], raw[12:16], raw[16:20], raw[20:]])


def parse_cookie_value(cookie, key):
    prefix = key + "="
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix) :]
    return ""


def parse_jwt_payload(token):
    if not token or "." not in token:
        return {}
    try:
        import base64

        payload = token.split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
    except Exception:
        return {}


def chrome_id_header(cookie):
    if getenv("TABBIT_DISABLE_CHROME_ID") == "1":
        return ""
    override = os.environ.get("TABBIT_CHROME_ID_CONSISTENCY_REQUEST")
    if override:
        return strip_header_prefix(override, "X-Chrome-ID-Consistency-Request")

    claims = parse_jwt_payload(parse_cookie_value(cookie, "token"))
    client_id = getenv("TABBIT_CHROME_CLIENT_ID", claims.get("azp", ""))
    sync_account_id = getenv(
        "TABBIT_CHROME_SYNC_ACCOUNT_ID",
        claims.get("sub") or claims.get("id") or parse_cookie_value(cookie, "user_id"),
    )
    device_id = getenv("TABBIT_CHROME_DEVICE_ID", "227e8eef-0e37-412b-b068-3f08cf0cc3f7")
    if not client_id or not sync_account_id or not device_id:
        return ""

    return ",".join(
        [
            "version=1",
            "client_id=%s" % client_id,
            "device_id=%s" % device_id,
            "sync_account_id=%s" % sync_account_id,
            "signin_mode=%s" % getenv("TABBIT_CHROME_SIGNIN_MODE", "all_accounts"),
            "signout_mode=%s" % getenv("TABBIT_CHROME_SIGNOUT_MODE", "show_confirmation"),
        ]
    )


def content_to_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def anthropic_prompt(payload):
    parts = []
    system_text = content_to_text(payload.get("system"))
    if system_text:
        parts.append("System:\n%s" % system_text)

    for message in payload.get("messages") or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role", "user")
        text = content_to_text(message.get("content"))
        if text:
            parts.append("%s:\n%s" % (role.capitalize(), text))

    return "\n\n".join(parts).strip() or "ping"


def openai_prompt(payload):
    parts = []
    instructions = content_to_text(payload.get("instructions"))
    if instructions:
        parts.append("Instructions:\n%s" % instructions)

    input_value = payload.get("input")
    if input_value is not None:
        if isinstance(input_value, list):
            for item in input_value:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    text = content_to_text(item.get("content"))
                    if text:
                        parts.append("%s:\n%s" % (role.capitalize(), text))
                else:
                    text = content_to_text(item)
                    if text:
                        parts.append(text)
        else:
            text = content_to_text(input_value)
            if text:
                parts.append(text)

    for message in payload.get("messages") or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role", "user")
        text = content_to_text(message.get("content"))
        if text:
            parts.append("%s:\n%s" % (role.capitalize(), text))

    return "\n\n".join(parts).strip() or "ping"


def model_aliases():
    mapping = dict(DEFAULT_MODEL_MAP)
    raw = os.environ.get("TABBIT_MODEL_MAP")
    if raw:
        try:
            configured = json.loads(raw)
            if isinstance(configured, dict):
                for key, value in configured.items():
                    if isinstance(key, str) and isinstance(value, str):
                        mapping[key] = value
        except Exception:
            pass
    return mapping


def tabbit_model(model):
    mapping = model_aliases()
    if model in mapping:
        return mapping[model]
    lowered = str(model or "").strip().lower()
    if lowered in mapping:
        return mapping[lowered]
    return getenv("TABBIT_SELECTED_MODEL", DEFAULT_MODEL)


def tabbit_body(content, model):
    session_id = getenv("TABBIT_SESSION_ID", DEFAULT_SESSION_ID)
    page_url = getenv("TABBIT_PAGE_URL", "")
    return {
        "agent_mode": False,
        "chat_session_id": session_id,
        "content": content,
        "entity": {
            "extras": {"type": getenv("TABBIT_ENTITY_TYPE", "tab"), "url": page_url},
            "key": getenv("TABBIT_ENTITY_KEY", DEFAULT_ENTITY_KEY),
        },
        "message_id": None,
        "metadatas": {"html_content": "<p>%s</p>" % html.escape(content)},
        "parallel_group_id": None,
        "references": [],
        "selected_model": tabbit_model(model),
        "task_name": "chat",
    }


def tabbit_headers(cookie):
    session_id = getenv("TABBIT_SESSION_ID", DEFAULT_SESSION_ID)
    referer = getenv("TABBIT_REFERER", "https://web.tabbit.ai/session/%s" % session_id)
    headers = {
        "Cache-Control": "no-cache",
        "sec-ch-ua-platform": '"macOS"',
        "sec-ch-ua": '"Chromium";v="148", "Tabbit";v="148", "Not/A)Brand";v="99"',
        "x-nonce": random.randbytes(32).hex() if hasattr(random, "randbytes") else os.urandom(32).hex(),
        "trace-id": str(uuid.uuid4()),
        "x-timestamp": str(int(time.time() * 1000)),
        "unique-uuid": tabbit_unique_uuid(getenv("TABBIT_IS_DEFAULT_BROWSER", "1") != "0"),
        "x-req-ctx": getenv("TABBIT_X_REQ_CTX", DEFAULT_REQ_CTX),
        "sec-ch-ua-mobile": "?0",
        "x-signature": str(uuid.uuid4()),
        "User-Agent": getenv("TABBIT_USER_AGENT", DEFAULT_USER_AGENT),
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "Origin": "https://web.tabbit.ai",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": referer,
        "Accept-Language": getenv("TABBIT_ACCEPT_LANGUAGE", "zh-CN,zh;q=0.9"),
        "Cookie": cookie,
        "x-glic": getenv("TABBIT_X_GLIC", "1"),
        "x-glic-chrome-version": getenv("TABBIT_GLIC_CHROME_VERSION", "148.0.7778.168"),
        "x-glic-chrome-channel": getenv("TABBIT_GLIC_CHROME_CHANNEL", "unknown"),
    }
    chrome_id = chrome_id_header(cookie)
    if chrome_id:
        headers["X-Chrome-ID-Consistency-Request"] = chrome_id
    return headers


def parse_sse_line_state(state, line):
    line = line.decode("utf-8", "replace").strip()
    if not line:
        return None
    if line.startswith("event:"):
        state["event"] = line[6:].strip()
        return None
    if line.startswith("data:"):
        data = line[5:].strip()
        try:
            return state.get("event", ""), json.loads(data) if data else {}
        except Exception:
            return state.get("event", ""), {}
    return None


def call_tabbit(content, model):
    cookie = read_cookie()
    body = json.dumps(tabbit_body(content, model), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        getenv("TABBIT_ENDPOINT", DEFAULT_ENDPOINT),
        data=body,
        headers=tabbit_headers(cookie),
        method="POST",
    )
    timeout = int(getenv("TABBIT_TIMEOUT_SECONDS", "180"))
    return urllib.request.urlopen(request, timeout=timeout)


def iter_tabbit_text(content, model):
    state = {}
    with call_tabbit(content, model) as response:
        for line in response:
            parsed = parse_sse_line_state(state, line)
            if not parsed:
                continue
            event, data = parsed
            if event == "message_chunk" and data.get("content"):
                yield data["content"]
            elif event == "error":
                raise RuntimeError(data.get("message") or "Tabbit upstream error")
            elif event in ("finish", "close"):
                break


def collect_tabbit_text(content, model):
    return "".join(iter_tabbit_text(content, model))


def anthropic_message_start(message_id, model):
    return {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }


def anthropic_response(text, model):
    return {
        "id": "msg_%s" % uuid.uuid4().hex,
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def openai_chat_response(text, model):
    return {
        "id": "chatcmpl_%s" % uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def openai_response(text, model):
    response_id = "resp_%s" % uuid.uuid4().hex
    output_id = "msg_%s" % uuid.uuid4().hex
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "model": model,
        "output": [
            {
                "id": output_id,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning": {"effort": None, "summary": None},
        "store": False,
        "temperature": None,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
        "truncation": "disabled",
        "usage": {
            "input_tokens": 0,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 0,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 0,
        },
    }


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_sse_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def route_path(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        return path or "/"

    def authorize(self):
        expected = os.environ.get("TABBIT_ADAPTER_API_KEY")
        if not expected:
            return True
        auth = self.headers.get("Authorization", "")
        x_api_key = self.headers.get("x-api-key", "")
        return x_api_key == expected or auth == "Bearer %s" % expected

    def do_GET(self):
        path = self.route_path()
        if path == "/health":
            self.send_json(200, {"ok": True})
        elif path == "/v1/models":
            self.send_json(
                200,
                {
                    "data": [
                        {
                            "id": "claude-opus-4-8",
                            "type": "model",
                            "display_name": "Claude Opus 4.8 via Tabbit",
                        }
                    ]
                },
            )
        else:
            self.send_json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        path = self.route_path()
        if path not in ("/v1/messages", "/v1/chat/completions", "/v1/responses"):
            self.send_json(404, {"error": {"message": "not found"}})
            return
        if not self.authorize():
            self.send_json(401, {"error": {"type": "authentication_error", "message": "unauthorized"}})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/v1/messages":
                self.handle_anthropic(payload)
            elif path == "/v1/chat/completions":
                self.handle_openai_chat(payload)
            else:
                self.handle_openai_response(payload)
        except Exception as exc:
            traceback.print_exc()
            self.send_json(502, {"error": {"type": "api_error", "message": str(exc)}})

    def with_tabbit_lock(self, callback):
        lock_timeout = int(getenv("TABBIT_LOCK_TIMEOUT_SECONDS", "600"))
        if not request_lock.acquire(True, lock_timeout):
            self.send_json(429, {"error": {"type": "rate_limit_error", "message": "Tabbit session is busy"}})
            return
        try:
            callback()
        finally:
            request_lock.release()

    def handle_anthropic(self, payload):
        stream = bool(payload.get("stream"))
        model = payload.get("model") or "claude-opus-4-8"
        content = anthropic_prompt(payload)

        def run():
            lock_timeout = int(getenv("TABBIT_LOCK_TIMEOUT_SECONDS", "600"))
            if stream:
                self.handle_anthropic_stream(content, model)
            else:
                self.handle_anthropic_non_stream(content, model)

        self.with_tabbit_lock(run)

    def handle_openai_chat(self, payload):
        stream = bool(payload.get("stream"))
        model = payload.get("model") or "claude-opus-4-8"
        content = openai_prompt(payload)

        def run():
            if stream:
                self.handle_openai_chat_stream(content, model)
            else:
                self.send_json(200, openai_chat_response(collect_tabbit_text(content, model), model))

        self.with_tabbit_lock(run)

    def handle_openai_response(self, payload):
        stream = bool(payload.get("stream"))
        model = payload.get("model") or "claude-opus-4-8"
        content = openai_prompt(payload)

        def run():
            if stream:
                self.handle_openai_response_stream(content, model)
            else:
                self.send_json(200, openai_response(collect_tabbit_text(content, model), model))

        self.with_tabbit_lock(run)

    def write_sse(self, event, data):
        payload = "event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))
        self.wfile.write(payload.encode("utf-8"))
        self.wfile.flush()

    def handle_anthropic_stream(self, content, model):
        self.send_sse_headers()

        message_id = "msg_%s" % uuid.uuid4().hex
        self.write_sse("message_start", anthropic_message_start(message_id, model))
        self.write_sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})

        try:
            for text in iter_tabbit_text(content, model):
                self.write_sse(
                    "content_block_delta",
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
                )
        except Exception as exc:
            self.write_sse("error", {"type": "error", "error": {"type": "api_error", "message": str(exc)}})
            self.close_connection = True
            return

        self.write_sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        self.write_sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 0},
            },
        )
        self.write_sse("message_stop", {"type": "message_stop"})
        self.close_connection = True

    def handle_anthropic_non_stream(self, content, model):
        self.send_json(200, anthropic_response(collect_tabbit_text(content, model), model))

    def handle_openai_chat_stream(self, content, model):
        self.send_sse_headers()
        chunk_id = "chatcmpl_%s" % uuid.uuid4().hex
        created = int(time.time())
        try:
            for text in iter_tabbit_text(content, model):
                payload = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                }
                self.wfile.write(("data: %s\n\n" % json.dumps(payload, ensure_ascii=False)).encode("utf-8"))
                self.wfile.flush()
            done = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            self.wfile.write(("data: %s\n\n" % json.dumps(done, ensure_ascii=False)).encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as exc:
            self.wfile.write(("data: %s\n\n" % json.dumps({"error": {"message": str(exc)}}, ensure_ascii=False)).encode("utf-8"))
            self.wfile.flush()
        self.close_connection = True

    def handle_openai_response_stream(self, content, model):
        self.send_sse_headers()
        response = openai_response("", model)
        item = response["output"][0]
        part = {"type": "output_text", "text": "", "annotations": []}
        self.write_sse("response.created", dict(response, status="in_progress", output=[]))
        self.write_sse("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": dict(item, content=[])})
        self.write_sse("response.content_part.added", {"type": "response.content_part.added", "item_id": item["id"], "output_index": 0, "content_index": 0, "part": part})
        chunks = []
        try:
            for text in iter_tabbit_text(content, model):
                chunks.append(text)
                self.write_sse(
                    "response.output_text.delta",
                    {
                        "type": "response.output_text.delta",
                        "item_id": item["id"],
                        "output_index": 0,
                        "content_index": 0,
                        "delta": text,
                    },
                )
        except Exception as exc:
            self.write_sse("response.failed", {"type": "response.failed", "response": dict(response, status="failed", error={"message": str(exc)})})
            self.close_connection = True
            return

        text = "".join(chunks)
        final_part = {"type": "output_text", "text": text, "annotations": []}
        final_item = dict(item, content=[final_part])
        final_response = dict(response, output=[final_item])
        self.write_sse("response.output_text.done", {"type": "response.output_text.done", "item_id": item["id"], "output_index": 0, "content_index": 0, "text": text})
        self.write_sse("response.content_part.done", {"type": "response.content_part.done", "item_id": item["id"], "output_index": 0, "content_index": 0, "part": final_part})
        self.write_sse("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": final_item})
        self.write_sse("response.completed", {"type": "response.completed", "response": final_response})
        self.close_connection = True


def main():
    host = getenv("TABBIT_ADAPTER_HOST", "127.0.0.1")
    port = int(getenv("TABBIT_ADAPTER_PORT", "18088"))
    server = ThreadingHTTPServer((host, port), Handler)
    print("tabbit anthropic adapter listening on %s:%s" % (host, port), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
