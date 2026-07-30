#!/usr/bin/env python3

import argparse
import base64
import binascii
import json
import pathlib
import struct
import sys
import urllib.error
import urllib.request
import zlib


DEFAULT_MODEL = "claude-4.8"


def read_env_value(path, name):
    for raw_line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip("'\"")
    return ""


def request_json(url, method="GET", payload=None, api_key="", timeout=300):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = {"error": {"message": "non-JSON HTTP error"}}
        return error.code, parsed


def message_text(payload):
    text = "".join(
        block.get("text", "")
        for block in payload.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    )
    if text:
        return text
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return ""


def tool_uses(payload):
    return [
        block
        for block in payload.get("content", [])
        if isinstance(block, dict) and block.get("type") == "tool_use"
    ]


def png_chunk(chunk_type, data):
    checksum = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", checksum)
    )


def quadrant_png(width=128, height=128):
    rows = []
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            if y < height // 2 and x < width // 2:
                row.extend((255, 0, 0))
            elif y < height // 2:
                row.extend((0, 255, 0))
            elif x < width // 2:
                row.extend((0, 0, 255))
            else:
                row.extend((255, 255, 0))
        rows.append(bytes(row))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + png_chunk(b"IEND", b"")
    )


def contains_ordered_quadrant_colors(text):
    lowered = text.lower()
    cursor = 0
    for alternatives in (("red", "红"), ("green", "绿"), ("blue", "蓝"), ("yellow", "黄")):
        positions = [
            lowered.find(alternative, cursor)
            for alternative in alternatives
        ]
        positions = [position for position in positions if position >= 0]
        if not positions:
            return False
        cursor = min(positions) + 1
    return True


def token_pdf(token):
    stream = ("BT /F1 18 Tf 72 720 Td (%s) Tj ET" % token).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, content in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(
            ("%s 0 obj\n" % number).encode("ascii")
            + content
            + b"\nendobj\n"
        )
    xref_offset = len(document)
    document.extend(("xref\n0 %s\n" % (len(objects) + 1)).encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(("%010d 00000 n \n" % offset).encode("ascii"))
    document.extend(
        (
            "trailer\n<< /Size %s /Root 1 0 R >>\n"
            "startxref\n%s\n%%%%EOF\n"
            % (len(objects) + 1, xref_offset)
        ).encode("ascii")
    )
    return bytes(document)


def anthropic_payload(content, tools=None, tool_choice=None):
    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": content}],
    }
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice
    return payload


def run_smoke(origin, api_key, timeout, include_attachments):
    messages_url = origin.rstrip("/") + "/v1/messages"
    health_status, health = request_json(
        origin.rstrip("/") + "/health",
        timeout=timeout,
    )
    unauthorized_status, _ = request_json(
        messages_url,
        method="POST",
        payload=anthropic_payload("Reply only AUTH_TEST"),
        timeout=timeout,
    )

    text_token = "FIGMA_TEXT_TOKEN_4821"
    text_status, text_response = request_json(
        messages_url,
        method="POST",
        payload=anthropic_payload("Reply only %s" % text_token),
        api_key=api_key,
        timeout=timeout,
    )
    text = message_text(text_response)

    tool_token = "FIGMA_TOOL_TOKEN_4821"
    tool_name = "return_test_token"
    tool_status, tool_response = request_json(
        messages_url,
        method="POST",
        payload=anthropic_payload(
            "Call the provided tool with token %s." % tool_token,
            tools=[
                {
                    "name": tool_name,
                    "description": "Return the exact supplied test token.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"token": {"type": "string"}},
                        "required": ["token"],
                    },
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        ),
        api_key=api_key,
        timeout=timeout,
    )
    calls = tool_uses(tool_response)
    tool_ok = (
        tool_status == 200
        and len(calls) == 1
        and calls[0].get("name") == tool_name
        and calls[0].get("input", {}).get("token") == tool_token
    )

    results = {
        "health": {
            "status": health_status,
            "passed": health_status == 200 and health.get("ok") is True,
        },
        "authentication": {
            "status": unauthorized_status,
            "passed": unauthorized_status == 401,
        },
        "text": {
            "status": text_status,
            "passed": text_status == 200 and text_token in text,
            "response": text[:160],
        },
        "tool_use": {
            "status": tool_status,
            "passed": tool_ok,
            "count": len(calls),
        },
    }

    if include_attachments:
        image_status, image_response = request_json(
            messages_url,
            method="POST",
            payload=anthropic_payload(
                [
                    {
                        "type": "text",
                        "text": (
                            "只看本条消息附加的图片，忽略当前画布和站点。"
                            "只回复四个象限的主要颜色，严格按左上、右上、"
                            "左下、右下顺序，用逗号分隔，可以用中文或英文。"
                        ),
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(
                                quadrant_png()
                            ).decode("ascii"),
                        },
                    },
                ]
            ),
            api_key=api_key,
            timeout=timeout,
        )
        image_text = message_text(image_response)
        image_ok = image_status == 200 and contains_ordered_quadrant_colors(
            image_text
        )

        pdf_token = "FIGMA_PDF_TOKEN_4821"
        pdf_status, pdf_response = request_json(
            messages_url,
            method="POST",
            payload=anthropic_payload(
                [
                    {
                        "type": "text",
                        "text": "读取 PDF，只回复其中唯一的全大写测试标记。",
                    },
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(
                                token_pdf(pdf_token)
                            ).decode("ascii"),
                        },
                    },
                ]
            ),
            api_key=api_key,
            timeout=timeout,
        )
        pdf_text = message_text(pdf_response)
        results["image"] = {
            "status": image_status,
            "passed": image_ok,
            "response": image_text[:160],
        }
        results["pdf"] = {
            "status": pdf_status,
            "passed": pdf_status == 200 and pdf_token in pdf_text,
            "response": pdf_text[:160],
        }

    return results


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Run a non-secret Figma Anthropic adapter smoke test."
    )
    parser.add_argument("--origin", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-attachments", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    api_key = read_env_value(args.env_file, "FIGMA_ADAPTER_API_KEY")
    if not api_key:
        raise SystemExit("FIGMA_ADAPTER_API_KEY is missing")
    results = run_smoke(
        args.origin,
        api_key,
        args.timeout,
        not args.skip_attachments,
    )
    print(json.dumps(results, ensure_ascii=True, sort_keys=True))
    if not all(item.get("passed") for item in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
