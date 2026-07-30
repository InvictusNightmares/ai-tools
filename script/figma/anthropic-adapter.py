#!/usr/bin/env python3

import base64
import binascii
import copy
import hashlib
import hmac
import json
import os
import re
import shlex
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


DEFAULT_ENDPOINT = "https://www.figma.com/api/cortex/shared/figmake"
DEFAULT_FIGMA_MODEL = "anthropic-claude-4.8-opus"
DEFAULT_PUBLIC_MODEL = "claude-4.8"
DEFAULT_MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_TEMPLATE_PROJECT_FILES = 64
RUNTIME_TEMPLATE_FORMAT = "figma-anthropic-runtime-template-v1"
FOUNDRY_SYNC_TEMPLATE_FORMAT = "figma-foundry-sync-runtime-template-v1"
SUPPORTED_IMAGE_TYPES = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)
FIGMA_TEMPLATE_HEADER_NAMES = {
    "tsid": "TSID",
    "x-figma-client-lifecycle-id": "X-Figma-Client-Lifecycle-ID",
    "x-figma-cortex-client-generated-request-uuid": (
        "X-Figma-Cortex-Client-Generated-Request-UUID"
    ),
    "x-figma-file-seq": "X-Figma-File-Seq",
    "x-figma-org-id": "X-Figma-Org-ID",
    "x-figma-owner-id": "X-Figma-Owner-ID",
    "x-figma-owner-type": "X-Figma-Owner-Type",
    "x-figma-persistent-entity-id": "X-Figma-Persistent-Entity-ID",
    "x-figma-support-request-id": "X-Figma-Support-Request-ID",
    "x-figma-team-id": "X-Figma-Team-ID",
    "x-referer-id": "X-Referer-ID",
    "x-referer-owner": "X-Referer-Owner",
    "x-referer-service": "X-Referer-Service",
    "x-referer-type": "X-Referer-Type",
}

request_lock = threading.Lock()
CLIENT_TOOL_CALL_OPEN = "<CLIENT_TOOL_CALL>"
CLIENT_TOOL_CALL_CLOSE = "</CLIENT_TOOL_CALL>"
CLIENT_TOOL_RESULT_OPEN = "<CLIENT_TOOL_RESULT>"
CLIENT_TOOL_RESULT_CLOSE = "</CLIENT_TOOL_RESULT>"


class RequestTooLarge(ValueError):
    pass


class UnsupportedAttachment(ValueError):
    pass


class UpstreamHTTPError(RuntimeError):
    def __init__(self, status, error_type, message, retry_after=None):
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.retry_after = retry_after


def getenv(name, default=""):
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def required_environment_value(name):
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError("%s is required" % name)
    return value


def read_required_startup_file(name):
    path = required_environment_value(name)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            contents = handle.read()
    except (OSError, UnicodeError):
        raise RuntimeError(
            "%s must name a readable non-empty file" % name
        ) from None
    if not contents.strip():
        raise RuntimeError("%s must name a readable non-empty file" % name)
    return contents


def positive_integer_environment(name, default):
    text = getenv(name, str(default))
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise RuntimeError("%s must be a positive integer" % name) from None
    if value <= 0:
        raise RuntimeError("%s must be a positive integer" % name)
    return value


def minimum_request_bytes_for_attachment(max_attachment_bytes):
    encoded_size = 4 * ((max_attachment_bytes + 2) // 3)
    request_without_data = {
        "model": DEFAULT_PUBLIC_MODEL,
        "max_tokens": 1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": "",
                        },
                    }
                ],
            }
        ],
    }
    envelope_size = len(
        json.dumps(
            request_without_data,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return encoded_size + envelope_size


def validate_startup_config():
    for name in (
        "FIGMA_ADAPTER_API_KEY",
        "FIGMA_USER_ID",
        "FIGMA_FILE_KEY",
        "FIGMA_THREAD_ID",
        "FIGMA_ATTACHMENT_GUID",
        "FIGMA_FOUNDRY_ORIGIN_HOST",
    ):
        required_environment_value(name)
    read_required_startup_file("FIGMA_COOKIE_FILE")
    template = read_required_startup_file("FIGMA_REQUEST_TEMPLATE_FILE")
    try:
        parse_runtime_request_template(template)
    except ValueError:
        raise RuntimeError(
            "FIGMA_REQUEST_TEMPLATE_FILE must contain a valid sanitized "
            "Figma request template"
        ) from None
    sync_template = read_required_startup_file(
        "FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE"
    )
    try:
        parse_foundry_sync_template(sync_template)
    except ValueError:
        raise RuntimeError(
            "FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE must contain a valid "
            "sanitized Figma Foundry sync template"
        ) from None
    attachment_guid = os.environ["FIGMA_ATTACHMENT_GUID"]
    if not re.fullmatch(r"[0-9]+:[0-9]+", attachment_guid):
        raise RuntimeError(
            "FIGMA_ATTACHMENT_GUID must use the numeric N:N format"
        )
    foundry_origin_host = os.environ["FIGMA_FOUNDRY_ORIGIN_HOST"]
    if (
        len(foundry_origin_host) > 253
        or not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",
            foundry_origin_host,
        )
        or not foundry_origin_host.lower().endswith(".figma.site")
    ):
        raise RuntimeError(
            "FIGMA_FOUNDRY_ORIGIN_HOST must be a figma.site hostname"
        )

    port = positive_integer_environment("FIGMA_ADAPTER_PORT", 18089)
    if port > 65535:
        raise RuntimeError(
            "FIGMA_ADAPTER_PORT must be between 1 and 65535"
        )
    max_request_bytes = positive_integer_environment(
        "FIGMA_MAX_REQUEST_BYTES",
        DEFAULT_MAX_REQUEST_BYTES,
    )
    max_attachment_bytes = positive_integer_environment(
        "FIGMA_MAX_ATTACHMENT_BYTES",
        DEFAULT_MAX_REQUEST_BYTES,
    )
    positive_integer_environment("FIGMA_TIMEOUT_SECONDS", 300)
    positive_integer_environment("FIGMA_LOCK_TIMEOUT_SECONDS", 600)
    minimum_request_bytes = minimum_request_bytes_for_attachment(
        max_attachment_bytes
    )
    if max_request_bytes < minimum_request_bytes:
        raise RuntimeError(
            "FIGMA_MAX_REQUEST_BYTES is too small for a base64 attachment "
            "at FIGMA_MAX_ATTACHMENT_BYTES"
        )
    return {"port": port}


def strip_header_prefix(value, name):
    trimmed = value.strip()
    prefix = name + ":"
    if trimmed.lower().startswith(prefix.lower()):
        return trimmed[len(prefix) :].strip()
    return trimmed


def read_cookie():
    if os.environ.get("FIGMA_COOKIE"):
        return strip_header_prefix(os.environ["FIGMA_COOKIE"], "Cookie")
    cookie_file = getenv(
        "FIGMA_COOKIE_FILE", "/opt/figma-claude/.figma-cookie.local"
    )
    with open(cookie_file, "r", encoding="utf-8") as handle:
        cookie = strip_header_prefix(handle.read(), "Cookie")
    if not cookie:
        raise RuntimeError("Figma cookie is empty")
    return cookie


def sanitize_structured_content(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key == "data" and isinstance(item, str) and len(item) > 256:
                sanitized[key] = "<omitted %s characters>" % len(item)
            else:
                sanitized[key] = sanitize_structured_content(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_structured_content(item) for item in value]
    return value


def protocol_json(value):
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def content_to_text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content_to_text([content])
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif item_type == "tool_result":
                tool_text = content_to_text(item.get("content"))
                if tool_text:
                    parts.append(
                        "%s%s%s"
                        % (
                            CLIENT_TOOL_RESULT_OPEN,
                            protocol_json(
                                {
                                    "tool_use_id": (
                                        item.get("tool_use_id") or "unknown"
                                    ),
                                    "is_error": bool(item.get("is_error")),
                                    "content": tool_text,
                                }
                            ),
                            CLIENT_TOOL_RESULT_CLOSE,
                        )
                    )
            elif item_type == "tool_use":
                parts.append(
                    "%s%s%s"
                    % (
                        CLIENT_TOOL_CALL_OPEN,
                        protocol_json(
                            {
                                "id": item.get("id") or "unknown",
                                "name": item.get("name", "unknown"),
                                "input": item.get("input", {}),
                            }
                        ),
                        CLIENT_TOOL_CALL_CLOSE,
                    )
                )
            elif item_type == "image":
                source = item.get("source") or {}
                media_type = (
                    source.get("media_type")
                    if isinstance(source, dict)
                    else None
                )
                parts.append("[Image attached: %s]" % (media_type or "unknown"))
            elif item_type == "document":
                source = item.get("source") or {}
                media_type = (
                    source.get("media_type")
                    if isinstance(source, dict)
                    else None
                )
                if media_type == "application/pdf":
                    parts.append("[PDF attached]")
                else:
                    parts.append(
                        "[Document attached: %s]" % (media_type or "unknown")
                    )
            elif item_type not in {"thinking", "redacted_thinking"}:
                parts.append(
                    "Structured content:\n%s"
                    % json.dumps(
                        sanitize_structured_content(item),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
        return "\n".join(parts)
    return str(content)


def unsupported_attachment(media_type):
    raise UnsupportedAttachment(
        "attachment media type %s is not supported; only JPEG, PNG, GIF, "
        "WebP images and PDF documents are supported"
        % (media_type or "unknown")
    )


def decode_attachment_source(source, media_type):
    if not isinstance(source, dict) or source.get("type") != "base64":
        raise UnsupportedAttachment(
            "attachment source type %s is not supported; use a base64 source"
            % (
                source.get("type", "unknown")
                if isinstance(source, dict)
                else "unknown"
            )
        )
    encoded = source.get("data")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("attachment base64 data must be a non-empty string")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("attachment contains invalid base64 data") from exc
    if not data:
        raise ValueError("attachment must not be empty")
    max_bytes = int(
        getenv("FIGMA_MAX_ATTACHMENT_BYTES", str(DEFAULT_MAX_REQUEST_BYTES))
    )
    if len(data) > max_bytes:
        raise RequestTooLarge(
            "attachment exceeds the %s byte limit" % max_bytes
        )
    return data


def figma_attachment_guid(document_index=0):
    configured = getenv("FIGMA_ATTACHMENT_GUID", "0:0")
    match = re.fullmatch(r"([0-9]+):([0-9]+)", configured)
    if not match:
        raise ValueError("FIGMA_ATTACHMENT_GUID must use the numeric N:N format")
    return "%s:%s" % (
        match.group(1),
        int(match.group(2)) + document_index,
    )


def attachment_from_block(block, document_index=0):
    if not isinstance(block, dict):
        return None
    block_type = block.get("type")
    if block_type not in {"image", "document", "video"}:
        return None

    source = block.get("source")
    media_type = (
        source.get("media_type") if isinstance(source, dict) else None
    )
    if block_type == "video":
        unsupported_attachment(media_type or "video")
    if block_type == "image":
        extension = SUPPORTED_IMAGE_TYPES.get(media_type)
        if not extension:
            unsupported_attachment(media_type)
        reference_type = "code-chat-image-import-ref"
        import_type = "image"
    else:
        if media_type != "application/pdf":
            unsupported_attachment(media_type)
        extension = "pdf"
        reference_type = "code-chat-pdf-import-ref"
        import_type = "pdf"

    data = decode_attachment_source(source, media_type)
    content_sha1 = hashlib.sha1(data).hexdigest()
    needs_binary_file = True
    label = "attachment-%s.%s" % (content_sha1[:12], extension)
    import_path = "/src/imports/%s" % label
    guid = figma_attachment_guid(document_index)
    message_descriptor = {
        "type": import_type,
        "guid": guid,
        "path": import_path,
    }
    if block_type == "image":
        message_descriptor.update(
            {
                "image": "data:%s;base64,%s"
                % (
                    media_type,
                    base64.b64encode(data).decode("ascii"),
                ),
                "imageHash": content_sha1,
            }
        )
    message_data = json.dumps(
        message_descriptor,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    message_content_type = "application/json"
    return {
        "data": data,
        "content_type": media_type,
        "content_sha1": content_sha1,
        "needs_binary_file": needs_binary_file,
        "message_data": message_data,
        "message_content_type": message_content_type,
        "message_sha1": hashlib.sha1(message_data).hexdigest(),
        "reference_type": reference_type,
        "import_path": import_path,
        "guid": guid,
        "label": label,
        "import_type": import_type,
    }


def iter_attachment_blocks(content):
    if isinstance(content, list):
        for item in content:
            yield from iter_attachment_blocks(item)
        return
    if not isinstance(content, dict):
        return
    if content.get("type") in {"image", "document", "video"}:
        yield content
        return
    if content.get("type") == "tool_result":
        yield from iter_attachment_blocks(content.get("content"))


def extract_attachments(payload):
    attachments = []
    seen = set()
    attachment_index = 0
    for message in payload.get("messages") or []:
        if not isinstance(message, dict):
            continue
        for block in iter_attachment_blocks(message.get("content")):
            attachment = attachment_from_block(block, attachment_index)
            if not attachment:
                continue
            key = (
                attachment["content_sha1"],
                attachment["reference_type"],
            )
            if key not in seen:
                seen.add(key)
                attachments.append(attachment)
                attachment_index += 1
    return attachments


def client_tools(payload):
    tool_choice = payload.get("tool_choice")
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "none":
        return []
    forced_name = None
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
        if isinstance(tool_choice.get("name"), str):
            forced_name = tool_choice["name"]

    tools = []
    for tool in payload.get("tools") or []:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            continue
        if forced_name and tool["name"] != forced_name:
            continue
        tools.append(
            {
                "name": tool["name"],
                "description": tool.get("description") or "",
                "input_schema": (
                    tool.get("input_schema")
                    if isinstance(tool.get("input_schema"), dict)
                    else {"type": "object"}
                ),
            }
        )
    return tools


def client_tool_protocol(tools, tool_choice=None):
    definitions = protocol_json(tools)
    forced_tool = ""
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
        name = tool_choice.get("name")
        if isinstance(name, str) and name:
            forced_tool = "\nYou must call the client tool named %s." % name
    elif isinstance(tool_choice, dict) and tool_choice.get("type") == "any":
        forced_tool = "\nYou must call at least one client tool."

    parallel_tools = not (
        isinstance(tool_choice, dict)
        and tool_choice.get("disable_parallel_tool_use") is True
    )
    call_count_instruction = (
        "You may emit multiple calls when they are independent; write each call "
        "in its own tag."
        if parallel_tools
        else "Emit exactly one tool call per response."
    )

    return (
        "Client tool protocol:\n"
        "You are operating as a coding agent. The client has explicitly authorized "
        "the tools listed below and will execute them for you. Do not invoke or "
        "render Figma built-in blocks such as Skill, Read, Write, Edit, or Bash. "
        "They are unavailable in this environment.\n"
        "When one or more client tools are needed, reply with only tool calls and "
        "no other text using this format:\n"
        '%s{"name":"ToolName","input":{}}%s\n'
        "Use only listed tools and follow each input_schema exactly. %s "
        "Earlier assistant calls use the same CLIENT_TOOL_CALL tags. Results from "
        "the client appear as %s"
        '{"tool_use_id":"...","is_error":false,"content":"..."}%s. '
        "After receiving a result, "
        "continue the task and call another tool if needed. When the task is "
        "complete, respond normally without the tool-call tags.%s\n"
        "Available client tools JSON:\n%s"
        % (
            CLIENT_TOOL_CALL_OPEN,
            CLIENT_TOOL_CALL_CLOSE,
            call_count_instruction,
            CLIENT_TOOL_RESULT_OPEN,
            CLIENT_TOOL_RESULT_CLOSE,
            forced_tool,
            definitions,
        )
    )


def anthropic_prompt(payload):
    parts = []
    system_text = content_to_text(payload.get("system"))
    if system_text:
        parts.append("System:\n%s" % system_text)

    tools = client_tools(payload)
    if tools:
        parts.append(client_tool_protocol(tools, payload.get("tool_choice")))

    for message in payload.get("messages") or []:
        if not isinstance(message, dict):
            continue
        text = content_to_text(message.get("content"))
        if text:
            parts.append("%s:\n%s" % (message.get("role", "user").capitalize(), text))

    if tools:
        parts.append("Assistant:")

    prompt = "\n\n".join(parts).strip()
    if not prompt:
        raise ValueError("messages must contain at least one text message")
    return prompt


def filtered_figma_template_headers(headers):
    if headers is None:
        return {}
    if isinstance(headers, dict):
        items = headers.items()
    elif isinstance(headers, (list, tuple)):
        items = headers
    else:
        raise ValueError("Figma request template headers must be an object")

    filtered = {}
    for item in items:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("Figma request template header is invalid")
        name, value = item
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        if "\r" in value or "\n" in value:
            raise ValueError("Figma request template header value is invalid")
        normalized = name.strip().lower()
        if normalized in FIGMA_TEMPLATE_HEADER_NAMES:
            filtered[normalized] = value.strip()
    return filtered


def parse_figma_request_template(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Figma request template is empty")

    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Figma request template contains invalid JSON"
            ) from exc
        if isinstance(parsed, dict) and "body" in parsed:
            if not isinstance(parsed.get("body"), dict):
                raise ValueError(
                    "Figma request template body must be a JSON object"
                )
            body = parsed["body"]
            headers = filtered_figma_template_headers(parsed.get("headers"))
        else:
            body = parsed
            headers = {}
        if not isinstance(body, dict):
            raise ValueError("Figma request template body must be a JSON object")
        return {"body": body, "headers": headers}

    command = stripped.replace("\\\r\n", "").replace("\\\n", "")
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError("Figma request template cURL is invalid") from exc
    if not tokens or os.path.basename(tokens[0]) != "curl":
        raise ValueError("Figma request template must be JSON or a cURL command")

    captured_headers = []
    bodies = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in {"-H", "--header"}:
            index += 1
            if index >= len(tokens):
                raise ValueError("Figma request template cURL is invalid")
            captured_headers.append(tokens[index])
        elif token.startswith("--header="):
            captured_headers.append(token.split("=", 1)[1])
        elif token.startswith("-H") and token != "-H":
            captured_headers.append(token[2:])
        elif token in {"--data", "--data-raw", "--data-binary", "-d"}:
            index += 1
            if index >= len(tokens):
                raise ValueError("Figma request template cURL is invalid")
            bodies.append(tokens[index])
        elif any(
            token.startswith(prefix)
            for prefix in (
                "--data=",
                "--data-raw=",
                "--data-binary=",
            )
        ):
            bodies.append(token.split("=", 1)[1])
        elif token in {"-b", "--cookie"}:
            index += 1
            if index >= len(tokens):
                raise ValueError("Figma request template cURL is invalid")
        index += 1

    if len(bodies) != 1:
        raise ValueError(
            "Figma request template cURL must contain exactly one JSON body"
        )
    if bodies[0].startswith("@"):
        raise ValueError(
            "Figma request template cURL cannot load an indirect body file"
        )
    try:
        body = json.loads(bodies[0])
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Figma request template contains invalid JSON"
        ) from exc
    if not isinstance(body, dict):
        raise ValueError("Figma request template body must be a JSON object")

    header_items = []
    for header in captured_headers:
        separator = header.find(":")
        if separator <= 0:
            raise ValueError("Figma request template cURL header is invalid")
        header_items.append(
            (
                header[:separator].strip(),
                header[separator + 1 :].strip(),
            )
        )
    return {
        "body": body,
        "headers": filtered_figma_template_headers(header_items),
    }


def validate_sanitized_template_body(body):
    if not isinstance(body, dict):
        raise ValueError("Figma runtime template body must be an object")

    files = body.get("files")
    if not isinstance(files, dict):
        raise ValueError("Figma runtime template files must be an object")
    if len(files) > MAX_TEMPLATE_PROJECT_FILES:
        raise ValueError("Figma runtime template has too many project files")
    for path, value in files.items():
        if not isinstance(path, str):
            raise ValueError("Figma runtime template file path is invalid")
        if isinstance(value, dict) and (
            value.get("type") == "binary"
            or "blobRef" in value
            or "mimeType" in value
        ):
            raise ValueError(
                "Figma runtime template cannot contain binary files"
            )

    file_metadata = body.get("fileMetadata")
    if not isinstance(file_metadata, list):
        raise ValueError(
            "Figma runtime template file metadata must be a list"
        )
    if len(file_metadata) != len(files):
        raise ValueError(
            "Figma runtime template file metadata must match project files"
        )
    metadata_guids = set()
    for entry in file_metadata:
        if not isinstance(entry, dict) or set(entry) != {"guid", "version"}:
            raise ValueError(
                "Figma runtime template file metadata is invalid"
            )
        guid = entry.get("guid")
        version = entry.get("version")
        if (
            not isinstance(guid, str)
            or not guid
            or not isinstance(version, str)
            or not version
            or any(character in guid for character in "\r\n\x00")
            or any(character in version for character in "\r\n\x00")
            or guid in metadata_guids
        ):
            raise ValueError(
                "Figma runtime template file metadata is invalid"
            )
        metadata_guids.add(guid)

    if body.get("chats") != []:
        raise ValueError("Figma runtime template chats must be empty")
    messages = body.get("aiChatMessages")
    if (
        not isinstance(messages, list)
        or len(messages) != 1
        or not isinstance(messages[0], dict)
        or messages[0].get("role") != "user"
        or messages[0].get("content") != []
    ):
        raise ValueError(
            "Figma runtime template must contain one empty user message"
        )
    for name in ("prompt", "rawPrompt", "text"):
        if name in messages[0]:
            raise ValueError(
                "Figma runtime template user message is not sanitized"
            )

    raw_details = body.get("rawUserChatDetails")
    if raw_details is not None and (
        not isinstance(raw_details, dict)
        or raw_details.get("rawUserMessage") != ""
        or raw_details.get("attachments") != []
    ):
        raise ValueError(
            "Figma runtime template raw user details are not sanitized"
        )
    user_content = body.get("userMessageContent")
    if user_content is not None and (
        not isinstance(user_content, dict)
        or user_content.get("plainText") != ""
        or user_content.get("imports") != []
    ):
        raise ValueError(
            "Figma runtime template user content is not sanitized"
        )
    for name in ("prompt", "rawPrompt", "rawUserMessage", "plainText"):
        if name in body and body[name] != "":
            raise ValueError(
                "Figma runtime template body is not sanitized"
            )


def parse_runtime_request_template(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Figma runtime template is empty")
    try:
        document = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Figma runtime template must be sanitized JSON"
        ) from exc
    if not isinstance(document, dict):
        raise ValueError("Figma runtime template must be an object")
    allowed_keys = {"format", "body", "headers", "config"}
    if set(document) - allowed_keys:
        raise ValueError("Figma runtime template contains unknown fields")
    if document.get("format") != RUNTIME_TEMPLATE_FORMAT:
        raise ValueError("Figma runtime template format is invalid")
    if not isinstance(document.get("headers"), dict):
        raise ValueError("Figma runtime template headers must be an object")
    for name, value in document["headers"].items():
        if (
            not isinstance(name, str)
            or name.strip().lower() not in FIGMA_TEMPLATE_HEADER_NAMES
            or not isinstance(value, str)
            or "\r" in value
            or "\n" in value
        ):
            raise ValueError("Figma runtime template header is invalid")

    config = document.get("config")
    allowed_config = {
        "FIGMA_USER_ID",
        "FIGMA_FILE_KEY",
        "FIGMA_THREAD_ID",
        "FIGMA_ATTACHMENT_GUID",
        "FIGMA_FOUNDRY_ORIGIN_HOST",
    }
    if config is not None:
        if not isinstance(config, dict) or set(config) - allowed_config:
            raise ValueError("Figma runtime template config is invalid")
        for value in config.values():
            if (
                not isinstance(value, str)
                or not value
                or "\r" in value
                or "\n" in value
                or "\x00" in value
            ):
                raise ValueError("Figma runtime template config is invalid")

    body = document.get("body")
    validate_sanitized_template_body(body)
    return {
        "body": body,
        "headers": filtered_figma_template_headers(document["headers"]),
    }


def load_figma_request_template():
    path = os.environ.get("FIGMA_REQUEST_TEMPLATE_FILE")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ValueError(
            "Figma request template file could not be read"
        ) from exc
    return parse_runtime_request_template(text)


def valid_sync_path(path):
    if (
        not isinstance(path, str)
        or not path
        or len(path) > 512
        or path.startswith("/")
        or any(character in path for character in "\r\n\x00")
    ):
        return False
    return all(segment not in {"", ".", ".."} for segment in path.split("/"))


def valid_sync_entrypoint_path(path):
    return (
        isinstance(path, str)
        and path.startswith("/")
        and valid_sync_path(path[1:])
    ) or valid_sync_path(path)


def valid_sync_metadata(metadata):
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"guid", "sha1Hash", "version"}
    ):
        return False
    guid = metadata.get("guid")
    sha1_hash = metadata.get("sha1Hash")
    version = metadata.get("version")
    return (
        isinstance(guid, str)
        and bool(guid)
        and isinstance(sha1_hash, str)
        and re.fullmatch(r"[0-9a-f]{40}", sha1_hash) is not None
        and isinstance(version, str)
        and bool(version)
        and not any(
            character in value
            for value in (guid, version)
            for character in "\r\n\x00"
        )
    )


def valid_sync_entry_metadata(metadata, file_metadata):
    if (
        not isinstance(metadata, dict)
        or set(metadata)
        != {
            "assetVersion",
            "collaborativeVersion",
            "guid",
            "makeLibraryId",
            "sha1Hash",
            "version",
        }
        or not valid_sync_metadata(file_metadata)
    ):
        return False
    for name in (
        "assetVersion",
        "collaborativeVersion",
        "guid",
        "makeLibraryId",
        "sha1Hash",
        "version",
    ):
        value = metadata.get(name)
        if not isinstance(value, str) or any(
            character in value for character in "\r\n\x00"
        ):
            return False
    return (
        bool(metadata["assetVersion"])
        and metadata["guid"] == file_metadata["guid"]
        and metadata["sha1Hash"] == file_metadata["sha1Hash"]
        and metadata["version"] == file_metadata["version"]
    )


def validate_foundry_sync_template_body(body):
    expected_keys = {
        "codeLastEditedBy",
        "codeLibraryFormat",
        "entrypointsByIdentifier",
        "featureType",
        "filePathToMetadata",
        "importedLibraryPaths",
        "originHost",
        "scopeKey",
        "scopeType",
        "selectedModel",
        "sourceCodeHash",
        "vfsChangeByPath",
    }
    if not isinstance(body, dict) or set(body) != expected_keys:
        raise ValueError("Figma Foundry sync template body is invalid")
    for name in (
        "codeLastEditedBy",
        "featureType",
        "originHost",
        "scopeKey",
        "scopeType",
        "selectedModel",
    ):
        value = body.get(name)
        if (
            not isinstance(value, str)
            or not value
            or any(character in value for character in "\r\n\x00")
        ):
            raise ValueError("Figma Foundry sync template body is invalid")
    if (
        not body["originHost"].lower().endswith(".figma.site")
        or not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",
            body["originHost"],
        )
        or not isinstance(body.get("codeLibraryFormat"), int)
        or isinstance(body.get("codeLibraryFormat"), bool)
        or body["codeLibraryFormat"] < 0
        or re.fullmatch(r"[0-9a-f]{40}", body.get("sourceCodeHash", ""))
        is None
    ):
        raise ValueError("Figma Foundry sync template body is invalid")

    entrypoints = body.get("entrypointsByIdentifier")
    if (
        not isinstance(entrypoints, dict)
        or len(entrypoints) > 32
        or not all(
            isinstance(key, str)
            and bool(key)
            and isinstance(value, str)
            and valid_sync_entrypoint_path(value)
            for key, value in entrypoints.items()
        )
    ):
        raise ValueError("Figma Foundry sync template entrypoints are invalid")
    imported_paths = body.get("importedLibraryPaths")
    if (
        not isinstance(imported_paths, list)
        or len(imported_paths) > 128
        or not all(valid_sync_path(path) for path in imported_paths)
    ):
        raise ValueError(
            "Figma Foundry sync template imported paths are invalid"
        )

    vfs = body.get("vfsChangeByPath")
    metadata_by_path = body.get("filePathToMetadata")
    if (
        not isinstance(vfs, dict)
        or not isinstance(metadata_by_path, dict)
        or len(vfs) > MAX_TEMPLATE_PROJECT_FILES + 8
        or len(metadata_by_path) > MAX_TEMPLATE_PROJECT_FILES + 8
    ):
        raise ValueError("Figma Foundry sync template files are invalid")
    for path, change in vfs.items():
        if (
            not valid_sync_path(path)
            or not isinstance(change, dict)
            or set(change) != {"entry", "type"}
            or change.get("type") != "upsert"
        ):
            raise ValueError("Figma Foundry sync template file is invalid")
        entry = change.get("entry")
        if (
            not isinstance(entry, dict)
            or set(entry) != {"contents", "metadata", "path"}
            or entry.get("path") != path
            or not isinstance(entry.get("contents"), str)
            or not valid_sync_entry_metadata(
                entry.get("metadata"),
                metadata_by_path.get(path),
            )
        ):
            raise ValueError("Figma Foundry sync template file is invalid")
    if not set(vfs).issubset(metadata_by_path):
        raise ValueError("Figma Foundry sync template metadata is invalid")
    for path, metadata in metadata_by_path.items():
        if not valid_sync_path(path) or not valid_sync_metadata(metadata):
            raise ValueError("Figma Foundry sync template metadata is invalid")


def parse_foundry_sync_template(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Figma Foundry sync template is empty")
    try:
        document = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Figma Foundry sync template must be sanitized JSON"
        ) from exc
    if (
        not isinstance(document, dict)
        or set(document) != {"format", "body", "headers"}
        or document.get("format") != FOUNDRY_SYNC_TEMPLATE_FORMAT
        or not isinstance(document.get("headers"), dict)
    ):
        raise ValueError("Figma Foundry sync template is invalid")
    headers = filtered_figma_template_headers(document["headers"])
    if len(headers) != len(document["headers"]):
        raise ValueError("Figma Foundry sync template header is invalid")
    validate_foundry_sync_template_body(document.get("body"))
    return {"body": document["body"], "headers": headers}


def load_foundry_sync_template():
    path = os.environ.get("FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ValueError(
            "Figma Foundry sync template file could not be read"
        ) from exc
    return parse_foundry_sync_template(text)


def merge_figma_request_template(current_body, request_template):
    template_body = (
        request_template.get("body")
        if isinstance(request_template, dict)
        else None
    )
    if not isinstance(template_body, dict):
        raise ValueError("Figma request template body must be a JSON object")

    merged = copy.deepcopy(template_body)
    template_messages = merged.get("aiChatMessages")
    template_user_message = None
    if isinstance(template_messages, list):
        for candidate in reversed(template_messages):
            if isinstance(candidate, dict) and candidate.get("role") == "user":
                template_user_message = candidate
                break

    current_message = current_body["aiChatMessages"][0]
    message = copy.deepcopy(template_user_message or {})
    message["role"] = "user"
    message["content"] = copy.deepcopy(current_message["content"])
    message["convertedFromScenegraph"] = True
    now_ms = int(time.time() * 1000)
    message["createdAtMs"] = now_ms
    message["scenegraphSentAt"] = str(now_ms)

    merged["model"] = current_body["model"]
    merged["aiChatMessages"] = [message]
    merged["aiChatThreadId"] = current_body["aiChatThreadId"]
    merged["numNewAiChatMessages"] = current_body["numNewAiChatMessages"]

    template_files = merged.get("files")
    if not isinstance(template_files, dict):
        template_files = {}
    merged_files = {
        path: copy.deepcopy(value)
        for path, value in template_files.items()
        if not (isinstance(value, dict) and value.get("type") == "binary")
    }
    merged_files.update(copy.deepcopy(current_body["files"]))
    merged["files"] = merged_files
    template_metadata = merged.get("fileMetadata")
    if not isinstance(template_metadata, list):
        template_metadata = []
    merged["fileMetadata"] = copy.deepcopy(
        template_metadata
    ) + copy.deepcopy(current_body.get("fileMetadata", []))
    merged["chats"] = copy.deepcopy(current_body["chats"])

    raw_details = merged.get("rawUserChatDetails")
    if not isinstance(raw_details, dict):
        raw_details = {}
    raw_details = copy.deepcopy(raw_details)
    raw_details.update(copy.deepcopy(current_body["rawUserChatDetails"]))
    merged["rawUserChatDetails"] = raw_details

    user_content = merged.get("userMessageContent")
    if not isinstance(user_content, dict):
        user_content = {}
    user_content = copy.deepcopy(user_content)
    user_content.update(copy.deepcopy(current_body["userMessageContent"]))
    merged["userMessageContent"] = user_content
    return merged


def figma_body(
    prompt,
    attachment_refs=None,
    attachments=None,
    request_template=None,
):
    content = [{"type": "text", "text": prompt}]
    references = attachment_refs or []
    content.extend(references)
    message = {
        "role": "user",
        "content": content,
    }
    body = {
        "model": getenv("FIGMA_SELECTED_MODEL", DEFAULT_FIGMA_MODEL),
        "aiChatMessages": [message],
        "files": {},
        "chats": [],
    }
    if not references:
        return body

    content.append({"chatMode": "build", "type": "code-chat-mode"})
    message["convertedFromScenegraph"] = True
    imports = []
    raw_attachments = []
    file_metadata = []
    for attachment in attachments or []:
        path = attachment.get("import_path")
        guid = attachment.get("guid")
        import_type = attachment.get("import_type")
        if not path or not guid or not import_type:
            continue
        body["files"][path] = {
            "blobRef": attachment["content_sha1"],
            "mimeType": attachment["content_type"],
            "type": "binary",
        }
        imports.append(
            {
                "guid": guid,
                "path": path,
                "type": import_type,
            }
        )
        raw_attachments.append(
            {
                "label": attachment["label"],
                "nodeGuid": guid,
                "type": import_type,
            }
        )
        file_metadata.append(
            {
                "guid": guid,
                "version": "",
            }
        )

    body.update(
        {
            "aiChatThreadId": getenv("FIGMA_THREAD_ID"),
            "fileMetadata": file_metadata,
            "numNewAiChatMessages": 1,
            "rawUserChatDetails": {
                "attachments": raw_attachments,
                "rawUserMessage": prompt,
            },
            "userMessageContent": {
                "chatMode": "build",
                "hidden": False,
                "imports": imports,
                "libraryKeys": [],
                "plainText": prompt,
                "selectedNodeIds": [],
            },
        }
    )
    if request_template is not None:
        return merge_figma_request_template(body, request_template)
    return body


def figma_headers(cookie, template_headers=None):
    user_id = getenv("FIGMA_USER_ID")
    file_key = getenv("FIGMA_FILE_KEY")
    if not user_id:
        raise RuntimeError("FIGMA_USER_ID is required")
    if not file_key:
        raise RuntimeError("FIGMA_FILE_KEY is required")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": cookie,
        "Origin": figma_api_origin(),
        "Referer": figma_referer(),
        "User-Agent": getenv("FIGMA_USER_AGENT", DEFAULT_USER_AGENT),
        "X-Csrf-Bypass": "yes",
        "X-Figma-User-ID": user_id,
        "X-Figma-File-Key": file_key,
    }
    for name, value in filtered_figma_template_headers(
        template_headers
    ).items():
        headers[FIGMA_TEMPLATE_HEADER_NAMES[name]] = value
    return headers


def figma_api_origin():
    configured = os.environ.get("FIGMA_API_ORIGIN")
    if configured:
        return configured.rstrip("/")
    endpoint = getenv("FIGMA_ENDPOINT", DEFAULT_ENDPOINT)
    parsed = urllib.parse.urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("FIGMA_ENDPOINT must be an absolute URL")
    return "%s://%s" % (parsed.scheme, parsed.netloc)


def figma_api_url(path):
    return figma_api_origin() + "/" + path.lstrip("/")


def figma_referer():
    configured = os.environ.get("FIGMA_REFERER")
    if configured:
        return configured
    file_key = getenv("FIGMA_FILE_KEY")
    return "%s/make/%s/" % (
        figma_api_origin(),
        urllib.parse.quote(file_key, safe=""),
    )


def url_origin(url):
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return None
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def upstream_error_details(status):
    if status == 429:
        return 429, "rate_limit_error"
    if status in {408, 504}:
        return 504, "timeout_error"
    if status in {502, 503, 529}:
        return 503, "overloaded_error"
    return 502, "api_error"


def decode_upstream_http_error(error):
    status, error_type = upstream_error_details(error.code)
    message = "Figma upstream returned HTTP %s" % error.code
    try:
        body = error.read(64 * 1024)
        data = json.loads(body.decode("utf-8", "replace"))
        if isinstance(data, dict):
            message = (
                figma_error_message(data)
                or data.get("message")
                or message
            )
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    retry_after = error.headers.get("Retry-After") if error.headers else None
    return UpstreamHTTPError(status, error_type, message, retry_after)


def post_figma_json(url, payload, cookie, template_headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=figma_headers(
            cookie,
            template_headers=template_headers,
        ),
        method="POST",
    )
    timeout = int(getenv("FIGMA_TIMEOUT_SECONDS", "300"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise decode_upstream_http_error(exc) from exc
    if not data:
        return {}
    try:
        result = json.loads(data.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Figma upload API returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Figma upload API returned an invalid response")
    if result.get("error") is True:
        raise RuntimeError(
            figma_error_message(result)
            or result.get("message")
            or "Figma upload API returned an error"
        )
    return result


def get_figma_json(url, cookie, template_headers=None):
    request = urllib.request.Request(
        url,
        headers=figma_headers(
            cookie,
            template_headers=template_headers,
        ),
        method="GET",
    )
    timeout = int(getenv("FIGMA_TIMEOUT_SECONDS", "300"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise decode_upstream_http_error(exc) from exc
    if not data:
        return {}
    try:
        result = json.loads(data.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Figma API returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Figma API returned an invalid response")
    if result.get("error") is True:
        raise RuntimeError(
            figma_error_message(result)
            or result.get("message")
            or "Figma API returned an error"
        )
    return result


def foundry_keep_alive_payload(request_template):
    template_body = (
        request_template.get("body")
        if isinstance(request_template, dict)
        else None
    )
    if not isinstance(template_body, dict):
        return None
    workload_config = template_body.get("workloadConfig")
    if not isinstance(workload_config, dict):
        return None
    payload = {
        "featureType": template_body.get("featureType"),
        "sboxAgentConfigId": "default",
        "scopeKey": template_body.get("scopeKey"),
        "scopeType": template_body.get("scopeType"),
        "workloadName": workload_config.get("workloadName"),
        "workspaceId": "default",
    }
    if not all(
        isinstance(value, str) and value
        for value in payload.values()
    ):
        return None
    return payload


def keep_foundry_alive(request_template):
    payload = foundry_keep_alive_payload(request_template)
    if payload is None:
        return
    template_headers = request_template.get("headers")
    post_figma_json(
        figma_api_url("/api/cortex/foundry/keep-alive"),
        payload,
        read_cookie(),
        template_headers=template_headers,
    )


def foundry_sandbox_payload(request_template):
    template_body = (
        request_template.get("body")
        if isinstance(request_template, dict)
        else None
    )
    if not isinstance(template_body, dict):
        return None
    workload_config = template_body.get("workloadConfig")
    if not isinstance(workload_config, dict):
        return None
    origin_host = getenv("FIGMA_FOUNDRY_ORIGIN_HOST")
    payload = {
        "featureType": template_body.get("featureType"),
        "forceProvision": False,
        "originHost": origin_host,
        "scopeKey": template_body.get("scopeKey"),
        "scopeType": template_body.get("scopeType"),
        "workloadConfig": {
            "sboxAgentConfigId": "default",
            "workloadName": workload_config.get("workloadName"),
        },
        "workspaceId": "default",
    }
    required_strings = (
        payload["featureType"],
        payload["originHost"],
        payload["scopeKey"],
        payload["scopeType"],
        payload["workloadConfig"]["sboxAgentConfigId"],
        payload["workloadConfig"]["workloadName"],
        payload["workspaceId"],
    )
    if not all(isinstance(value, str) and value for value in required_strings):
        return None
    return payload


def provision_foundry_sandbox(request_template):
    payload = foundry_sandbox_payload(request_template)
    if payload is None:
        return request_template
    response = post_figma_json(
        figma_api_url("/api/cortex/foundry/sandbox"),
        payload,
        read_cookie(),
        template_headers=request_template.get("headers"),
    )
    sboxd_url = response.get("sboxdUrl")
    parsed = (
        urllib.parse.urlparse(sboxd_url)
        if isinstance(sboxd_url, str)
        else None
    )
    if (
        parsed is None
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise RuntimeError(
            "Figma Foundry sandbox response is missing a valid sboxdUrl"
        )
    refreshed = copy.deepcopy(request_template)
    refreshed["body"]["sboxdUrl"] = sboxd_url
    return refreshed


def valid_figma_blob_download_url(url):
    if not isinstance(url, str) or len(url) > 8192:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.figma.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/blobs/")
        or parsed.path == "/blobs/"
        or parsed.fragment
    ):
        return False
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    required = {
        "X-Amz-Algorithm",
        "X-Amz-Credential",
        "X-Amz-Date",
        "X-Amz-Expires",
        "X-Amz-Signature",
        "X-Amz-SignedHeaders",
    }
    return all(
        len(query.get(name, [])) == 1 and bool(query[name][0])
        for name in required
    )


def list_make_binary_files(cookie, template_headers=None):
    file_key = getenv("FIGMA_FILE_KEY")
    encoded_file_key = urllib.parse.quote(file_key, safe="")
    query = urllib.parse.urlencode({"file_key": file_key})
    response = get_figma_json(
        figma_api_url(
            "/api/make/%s/binary_files?%s" % (encoded_file_key, query)
        ),
        cookie,
        template_headers=template_headers,
    )
    meta = response.get("meta")
    content_blobs = (
        meta.get("content_blobs") if isinstance(meta, dict) else None
    )
    if not isinstance(content_blobs, dict):
        raise RuntimeError(
            "Figma binary file list is missing content blobs"
        )
    return content_blobs


def foundry_attachment_target(attachment):
    content_sha1 = attachment.get("content_sha1")
    import_path = attachment.get("import_path")
    guid = attachment.get("guid")
    mime_type = attachment.get("content_type")
    sync_path = (
        import_path[1:]
        if isinstance(import_path, str)
        and import_path.startswith("/src/imports/")
        else None
    )
    if (
        not isinstance(content_sha1, str)
        or re.fullmatch(r"[0-9a-f]{40}", content_sha1) is None
        or not valid_sync_path(sync_path)
        or not isinstance(guid, str)
        or not guid
        or any(character in guid for character in "\r\n\x00")
        or mime_type
        not in set(SUPPORTED_IMAGE_TYPES) | {"application/pdf"}
    ):
        raise RuntimeError("Figma attachment metadata is invalid")
    return content_sha1, sync_path, guid, mime_type


def validate_foundry_attachment_targets(sync_body, attachments):
    vfs = sync_body.get("vfsChangeByPath")
    metadata_by_path = sync_body.get("filePathToMetadata")
    if not isinstance(vfs, dict) or not isinstance(metadata_by_path, dict):
        raise RuntimeError("Figma Foundry sync template files are invalid")
    occupied_paths = set(vfs) | set(metadata_by_path)
    for attachment in attachments or []:
        if not attachment.get("needs_binary_file"):
            continue
        _content_sha1, sync_path, _guid, _mime_type = (
            foundry_attachment_target(attachment)
        )
        if sync_path in occupied_paths:
            raise RuntimeError(
                "Figma attachment path conflicts with the sync template"
            )
        occupied_paths.add(sync_path)


def add_foundry_attachment_changes(sync_body, attachments, content_blobs):
    validate_foundry_attachment_targets(sync_body, attachments)
    vfs = sync_body["vfsChangeByPath"]
    metadata_by_path = sync_body["filePathToMetadata"]

    for attachment in attachments or []:
        if not attachment.get("needs_binary_file"):
            continue
        content_sha1, sync_path, guid, mime_type = (
            foundry_attachment_target(attachment)
        )
        download_url = content_blobs.get(content_sha1)
        if not valid_figma_blob_download_url(download_url):
            raise RuntimeError(
                "Figma binary file list is missing a safe download URL "
                "for %s" % content_sha1
            )
        vfs[sync_path] = {
            "entry": {
                "downloadUrl": download_url,
                "metadata": {
                    "assetVersion": "",
                    "blobRef": content_sha1,
                    "guid": guid,
                    "mimeType": mime_type,
                    "version": "",
                },
                "path": sync_path,
            },
            "type": "upsert",
        }
        metadata_by_path[sync_path] = {
            "guid": guid,
            "version": "",
        }


def prepare_foundry_sync(
    sync_template,
    request_template,
    attachments=None,
):
    if sync_template is None:
        return None
    if not isinstance(request_template, dict):
        raise RuntimeError(
            "Figma Foundry sync requires a request runtime template"
        )
    sync_body = copy.deepcopy(sync_template["body"])
    request_body = request_template.get("body")
    if not isinstance(request_body, dict):
        raise RuntimeError(
            "Figma Foundry sync requires a request runtime template"
        )
    expected_context = {
        "featureType": request_body.get("featureType"),
        "originHost": getenv("FIGMA_FOUNDRY_ORIGIN_HOST"),
        "scopeKey": request_body.get("scopeKey"),
        "scopeType": request_body.get("scopeType"),
    }
    if any(
        not isinstance(value, str) or not value
        for value in expected_context.values()
    ):
        raise RuntimeError("Figma Foundry sync context is incomplete")
    for name, value in expected_context.items():
        if sync_body.get(name) != value:
            raise RuntimeError(
                "Figma Foundry sync context does not match %s" % name
            )
    template_headers = dict(request_template.get("headers") or {})
    template_headers.update(sync_template.get("headers") or {})
    validate_foundry_attachment_targets(sync_body, attachments)
    return {
        "body": sync_body,
        "headers": template_headers,
    }


def sync_foundry_sandbox(
    prepared_sync,
    attachments=None,
    cookie=None,
):
    if prepared_sync is None:
        return
    sync_body = copy.deepcopy(prepared_sync["body"])
    template_headers = prepared_sync["headers"]
    if attachments:
        cookie = cookie or read_cookie()
        content_blobs = list_make_binary_files(
            cookie,
            template_headers=template_headers,
        )
        add_foundry_attachment_changes(
            sync_body,
            attachments,
            content_blobs,
        )
    post_figma_json(
        figma_api_url("/api/cortex/foundry/sync"),
        sync_body,
        cookie or read_cookie(),
        template_headers=template_headers,
    )


def upload_package(response, content_sha1):
    meta = response.get("meta")
    packages = (
        meta.get("upload_packages")
        if isinstance(meta, dict)
        else None
    )
    entry = packages.get(content_sha1) if isinstance(packages, dict) else None
    if not isinstance(entry, dict):
        raise RuntimeError(
            "Figma upload API did not return a package for %s" % content_sha1
        )
    error_message = entry.get("error_message")
    if error_message:
        if "already exists" in str(error_message).lower():
            return None
        raise RuntimeError(str(error_message))
    package = entry.get("package")
    if not isinstance(package, dict):
        raise RuntimeError("Figma upload package is missing")
    if not isinstance(package.get("fields"), dict):
        raise RuntimeError("Figma upload package fields are missing")
    if not isinstance(package.get("upload_url"), str):
        raise RuntimeError("Figma upload URL is missing")
    return package


def multipart_body(fields, data, content_type):
    boundary = "----FigmaAdapter%s" % uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.extend(
            [
                "--%s\r\n" % boundary,
                'Content-Disposition: form-data; name="%s"\r\n\r\n'
                % str(name).replace('"', ""),
                str(value),
                "\r\n",
            ]
        )
    prefix = "".join(chunks).encode("utf-8")
    file_header = (
        "--%s\r\n"
        'Content-Disposition: form-data; name="file"; filename="blob"\r\n'
        "Content-Type: %s\r\n\r\n"
        % (boundary, content_type)
    ).encode("utf-8")
    suffix = ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    return boundary, prefix + file_header + data + suffix


def multipart_policy_fields(fields):
    encoded_policy = fields.get("policy")
    if not isinstance(encoded_policy, str) or not encoded_policy:
        return {}
    padding = "=" * (-len(encoded_policy) % 4)
    try:
        policy = json.loads(
            base64.b64decode(
                encoded_policy + padding,
                validate=True,
            ).decode("utf-8")
        )
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Figma upload policy is invalid")

    referenced = {}
    conditions = (
        policy.get("conditions") if isinstance(policy, dict) else None
    )
    for condition in conditions or []:
        if (
            isinstance(condition, list)
            and len(condition) >= 2
            and isinstance(condition[1], str)
            and condition[1].startswith("$")
        ):
            name = condition[1][1:]
            referenced[name.lower()] = name
        elif isinstance(condition, dict):
            for name in condition:
                if isinstance(name, str):
                    referenced[name.lower()] = name
    return referenced


def multipart_form_fields(fields, data, content_type):
    prepared = dict(fields)
    referenced = multipart_policy_fields(fields)
    content_type_field = referenced.get("content-type")
    if content_type_field:
        prepared[content_type_field] = content_type
    checksum_field = referenced.get("x-amz-checksum-sha1")
    if checksum_field:
        prepared[checksum_field] = base64.b64encode(
            hashlib.sha1(data).digest()
        ).decode("ascii")
    return prepared


def multipart_headers(cookie, upload_url, boundary):
    origin = figma_api_origin()
    headers = {
        "Accept": "*/*",
        "Content-Type": "multipart/form-data; boundary=%s" % boundary,
        "Origin": origin,
        "User-Agent": getenv("FIGMA_USER_AGENT", DEFAULT_USER_AGENT),
    }
    if url_origin(upload_url) == url_origin(origin):
        headers["Cookie"] = cookie
        headers["Referer"] = figma_referer()
    return headers


def post_multipart_package(package, data, content_type, cookie):
    upload_url = package["upload_url"]
    parsed = urllib.parse.urlparse(upload_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("Figma upload URL is invalid")
    boundary, body = multipart_body(
        multipart_form_fields(package["fields"], data, content_type),
        data,
        content_type,
    )
    request = urllib.request.Request(
        upload_url,
        data=body,
        headers=multipart_headers(cookie, upload_url, boundary),
        method="POST",
    )
    timeout = int(getenv("FIGMA_TIMEOUT_SECONDS", "300"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise decode_upstream_http_error(exc) from exc


def upload_make_binary(attachment, cookie):
    file_key = getenv("FIGMA_FILE_KEY")
    files = [
        {
            "content_sha1": attachment["content_sha1"],
            "content_type": attachment["content_type"],
        }
    ]
    payload = {"file_key": file_key, "files": files}
    encoded_file_key = urllib.parse.quote(file_key, safe="")
    init_response = post_figma_json(
        figma_api_url(
            "/api/make/%s/binary_files/init_uploads" % encoded_file_key
        ),
        payload,
        cookie,
    )
    package = upload_package(init_response, attachment["content_sha1"])
    if package is not None:
        post_multipart_package(
            package,
            attachment["data"],
            attachment["content_type"],
            cookie,
        )
        commit_key = package.get("commit_key")
        if not isinstance(commit_key, str) or not commit_key:
            raise RuntimeError("Figma upload commit key is missing")
        post_figma_json(
            figma_api_url(
                "/api/make/%s/binary_files/commit_uploads"
                % encoded_file_key
            ),
            {"commit_keys": [commit_key]},
            cookie,
        )
    post_figma_json(
        figma_api_url(
            "/api/make/%s/binary_files/add_references"
            % encoded_file_key
        ),
        payload,
        cookie,
    )


def upload_message_content(attachment, cookie, thread_id):
    file_key = getenv("FIGMA_FILE_KEY")
    encoded_file_key = urllib.parse.quote(file_key, safe="")
    encoded_thread_id = urllib.parse.quote(thread_id, safe="")
    init_payload = {
        "content_sha1s": [attachment["message_sha1"]],
        "file_key": file_key,
        "thread_id": thread_id,
    }
    init_response = post_figma_json(
        figma_api_url(
            "/api/ai_chat/%s/message_content_blobs/%s/init_uploads"
            % (encoded_file_key, encoded_thread_id)
        ),
        init_payload,
        cookie,
    )
    package = upload_package(init_response, attachment["message_sha1"])
    if package is not None:
        post_multipart_package(
            package,
            attachment["message_data"],
            attachment["message_content_type"],
            cookie,
        )
        commit_key = package.get("commit_key")
        if not isinstance(commit_key, str) or not commit_key:
            raise RuntimeError("Figma upload commit key is missing")
        post_figma_json(
            figma_api_url(
                "/api/ai_chat/%s/message_content_blobs/commit_uploads"
                % encoded_file_key
            ),
            {"commit_keys": [commit_key]},
            cookie,
        )
    return {
        "blobstoreContentKey": attachment["message_sha1"],
        "type": attachment["reference_type"],
    }


def upload_attachments(attachments):
    if not attachments:
        return []
    thread_id = getenv("FIGMA_THREAD_ID")
    if not thread_id:
        raise ValueError("FIGMA_THREAD_ID is required for image and PDF attachments")
    cookie = read_cookie()
    references = []
    for attachment in attachments:
        if attachment["needs_binary_file"]:
            upload_make_binary(attachment, cookie)
        references.append(
            upload_message_content(attachment, cookie, thread_id)
        )
    return references


def call_figma(
    prompt,
    attachment_refs=None,
    attachments=None,
    request_template=None,
):
    body = json.dumps(
        figma_body(
            prompt,
            attachment_refs,
            attachments,
            request_template=request_template,
        ),
        ensure_ascii=False,
    ).encode("utf-8")
    template_headers = (
        request_template.get("headers")
        if isinstance(request_template, dict)
        else None
    )
    request = urllib.request.Request(
        getenv("FIGMA_ENDPOINT", DEFAULT_ENDPOINT),
        data=body,
        headers=figma_headers(
            read_cookie(),
            template_headers=template_headers,
        ),
        method="POST",
    )
    timeout = int(getenv("FIGMA_TIMEOUT_SECONDS", "300"))
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise decode_upstream_http_error(exc) from exc


def parse_sse_data(line):
    text = line.decode("utf-8", "replace").strip()
    if not text.startswith("data:"):
        return None
    data = text[5:].strip()
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def figma_error_message(data):
    cortex_error = data.get("cortex_error")
    if isinstance(cortex_error, dict):
        details = cortex_error.get("data") or {}
        return details.get("message") or cortex_error.get("type") or "Figma error"
    if data.get("marker") or data.get("statusCode"):
        return data.get("message") or "Figma provider error"
    return ""


def read_figma_response(response, on_text):
    output = []
    for line in response:
        data = parse_sse_data(line)
        if not data:
            continue

        error = figma_error_message(data)
        if error:
            raise RuntimeError(error)

        event_type = data.get("type")
        if event_type == "visible_message":
            text = data.get("message")
            if isinstance(text, str) and text:
                output.append(text)
                on_text(text)
        elif event_type == "finish":
            break

    return "".join(output)


def approximate_tokens(text):
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def count_tokens_response(payload):
    return {"input_tokens": approximate_tokens(anthropic_prompt(payload))}


def anthropic_error(error_type, message):
    return {
        "type": "error",
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def parse_client_tool_calls(text, allowed_tool_names):
    if not isinstance(text, str):
        return []

    pattern = re.escape(CLIENT_TOOL_CALL_OPEN) + r"\s*(.*?)\s*" + re.escape(
        CLIENT_TOOL_CALL_CLOSE
    )
    matches = list(re.finditer(pattern, text, re.DOTALL))
    if not matches:
        return []

    last_match = matches[-1]
    if text[last_match.end() :].strip():
        return []

    selected_matches = [last_match]
    suffix_start = last_match.start()
    for match in reversed(matches[:-1]):
        if text[match.end() : suffix_start].strip():
            break
        selected_matches.append(match)
        suffix_start = match.start()
    selected_matches.reverse()

    line_start = max(
        text.rfind("\n", 0, suffix_start),
        text.rfind("\r", 0, suffix_start),
    ) + 1
    line_prefix = text[line_start:suffix_start]
    if line_prefix.strip() or len(line_prefix.expandtabs(4)) >= 4:
        return []

    prefix = text[:suffix_start]
    if prefix.count("```") % 2 or prefix.count("~~~") % 2:
        return []

    allowed = set(allowed_tool_names or [])
    calls = []
    for match in selected_matches:
        try:
            call = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        if not isinstance(call, dict):
            return []
        name = call.get("name")
        tool_input = call.get("input", {})
        if (
            not isinstance(name, str)
            or name not in allowed
            or not isinstance(tool_input, dict)
        ):
            return []
        calls.append({"name": name, "input": tool_input})
    return calls


def parse_client_tool_call(text, allowed_tool_names):
    calls = parse_client_tool_calls(text, allowed_tool_names)
    return calls[0] if calls else None


def client_visible_text(text):
    markers = (
        CLIENT_TOOL_CALL_OPEN,
        CLIENT_TOOL_CALL_CLOSE,
        CLIENT_TOOL_RESULT_OPEN,
        CLIENT_TOOL_RESULT_CLOSE,
    )
    if isinstance(text, str) and any(marker in text for marker in markers):
        return "The upstream model returned an invalid client tool response. Please retry."
    return text


def anthropic_tool_use(call):
    return {
        "type": "tool_use",
        "id": "toolu_%s" % uuid.uuid4().hex,
        "name": call["name"],
        "input": call["input"],
    }


def anthropic_message_start(message_id, model, input_tokens):
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
            "usage": {"input_tokens": input_tokens, "output_tokens": 0},
        },
    }


def anthropic_response(text, model, input_tokens, allowed_tool_names=None):
    calls = parse_client_tool_calls(text, allowed_tool_names)
    if calls:
        content = [anthropic_tool_use(call) for call in calls]
        stop_reason = "tool_use"
        visible_text = text
    else:
        visible_text = client_visible_text(text)
        content = [{"type": "text", "text": visible_text}]
        stop_reason = "end_turn"

    return {
        "id": "msg_%s" % uuid.uuid4().hex,
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": approximate_tokens(visible_text),
        },
    }


def tool_use_stream_events(tool_use, index=0):
    return [
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": index,
                "content_block": {
                    "type": "tool_use",
                    "id": tool_use["id"],
                    "name": tool_use["name"],
                    "input": {},
                },
            },
        ),
        (
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": index,
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": json.dumps(
                        tool_use["input"],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            },
        ),
        (
            "content_block_stop",
            {"type": "content_block_stop", "index": index},
        ),
    ]


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, status, payload, include_body=True, headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if include_body:
            self.wfile.write(data)

    def route_path(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        return path or "/"

    def authorize(self):
        expected = os.environ.get("FIGMA_ADAPTER_API_KEY")
        if not expected:
            return True
        auth = self.headers.get("Authorization", "")
        x_api_key = self.headers.get("x-api-key", "")
        return hmac.compare_digest(x_api_key, expected) or hmac.compare_digest(
            auth,
            "Bearer %s" % expected,
        )

    def read_json_payload(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("chunked request bodies are not supported")

        length_text = self.headers.get("Content-Length")
        if length_text is None:
            raise ValueError("Content-Length is required")
        length = int(length_text)
        if length <= 0:
            raise ValueError("request body must not be empty")

        max_bytes = int(
            getenv("FIGMA_MAX_REQUEST_BYTES", str(DEFAULT_MAX_REQUEST_BYTES))
        )
        if length > max_bytes:
            raise RequestTooLarge(
                "request body exceeds the %s byte limit" % max_bytes
            )
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def hello_payload(self):
        return {
            "ok": True,
            "service": "figma-anthropic-adapter",
            "capabilities": {
                "messages": True,
                "streaming": True,
                "tool_use": True,
                "count_tokens": True,
                "image_attachments": True,
                "pdf_attachments": True,
                "attachment_runtime_template_configured": bool(
                    os.environ.get("FIGMA_REQUEST_TEMPLATE_FILE")
                ),
                "foundry_sync_template_configured": bool(
                    os.environ.get("FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE")
                ),
            },
        }

    def do_HEAD(self):
        path = self.route_path()
        if path in {"/api/hello", "/health"}:
            self.send_json(200, self.hello_payload(), include_body=False)
        elif path == "/v1/models":
            self.send_json(200, {"data": []}, include_body=False)
        else:
            self.send_json(
                404,
                anthropic_error("not_found_error", "not found"),
                include_body=False,
            )

    def do_GET(self):
        path = self.route_path()
        if path in {"/api/hello", "/health"}:
            self.send_json(200, self.hello_payload())
        elif path == "/v1/models":
            self.send_json(
                200,
                {
                    "data": [
                        {
                            "id": DEFAULT_PUBLIC_MODEL,
                            "type": "model",
                            "display_name": "Claude 4.8 via Figma",
                        },
                        {
                            "id": "claude-opus-4-8",
                            "type": "model",
                            "display_name": "Claude Opus 4.8 via Figma",
                        },
                    ]
                },
            )
        else:
            self.send_json(
                404,
                anthropic_error("not_found_error", "not found"),
            )

    def do_POST(self):
        path = self.route_path()
        if path not in {"/v1/messages", "/v1/messages/count_tokens"}:
            self.send_json(
                404,
                anthropic_error("not_found_error", "not found"),
            )
            return
        if not self.authorize():
            self.send_json(
                401,
                anthropic_error("authentication_error", "unauthorized"),
            )
            return

        try:
            payload = self.read_json_payload()
            if path == "/v1/messages/count_tokens":
                self.send_json(200, count_tokens_response(payload))
                return

            attachments = extract_attachments(payload)
            prompt = anthropic_prompt(payload)
            stream = bool(payload.get("stream"))
            model = payload.get("model") or DEFAULT_PUBLIC_MODEL
            tool_names = {tool["name"] for tool in client_tools(payload)}
            request_template = (
                load_figma_request_template() if attachments else None
            )
            sync_template = (
                load_foundry_sync_template() if attachments else None
            )
            prepared_sync = prepare_foundry_sync(
                sync_template,
                request_template,
                attachments=attachments,
            )
            lock_timeout = int(getenv("FIGMA_LOCK_TIMEOUT_SECONDS", "600"))

            if not request_lock.acquire(True, lock_timeout):
                self.send_json(
                    429,
                    anthropic_error(
                        "rate_limit_error",
                        "Figma session is busy",
                    ),
                )
                return

            try:
                keep_foundry_alive(request_template)
                request_template = provision_foundry_sandbox(request_template)
                if request_template is not None:
                    keep_foundry_alive(request_template)
                attachment_refs = upload_attachments(attachments)
                sync_foundry_sandbox(
                    prepared_sync,
                    attachments=attachments,
                )
                if stream:
                    self.handle_stream(
                        prompt,
                        model,
                        tool_names,
                        attachment_refs,
                        attachments,
                        request_template,
                    )
                else:
                    self.handle_non_stream(
                        prompt,
                        model,
                        tool_names,
                        attachment_refs,
                        attachments,
                        request_template,
                    )
            finally:
                request_lock.release()
        except UpstreamHTTPError as exc:
            headers = {}
            if exc.retry_after:
                headers["Retry-After"] = exc.retry_after
            self.send_json(
                exc.status,
                anthropic_error(exc.error_type, str(exc)),
                headers=headers,
            )
        except RequestTooLarge as exc:
            self.send_json(
                413,
                anthropic_error("invalid_request_error", str(exc)),
            )
        except ValueError as exc:
            self.send_json(
                400,
                anthropic_error("invalid_request_error", str(exc)),
            )
        except Exception as exc:
            traceback.print_exc()
            self.send_json(
                502,
                anthropic_error("api_error", str(exc)),
            )

    def write_sse(self, event, data):
        payload = "event: %s\ndata: %s\n\n" % (
            event,
            json.dumps(data, ensure_ascii=False),
        )
        self.wfile.write(payload.encode("utf-8"))
        self.wfile.flush()

    def handle_stream(
        self,
        prompt,
        model,
        tool_names,
        attachment_refs=None,
        attachments=None,
        request_template=None,
    ):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        message_id = "msg_%s" % uuid.uuid4().hex
        input_tokens = approximate_tokens(prompt)
        output_tokens = 0

        self.write_sse(
            "message_start",
            anthropic_message_start(message_id, model, input_tokens),
        )

        def on_text(text):
            nonlocal output_tokens
            output_tokens += approximate_tokens(text)
            self.write_sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                },
            )

        try:
            if tool_names:
                with call_figma(
                    prompt,
                    attachment_refs,
                    attachments,
                    request_template,
                ) as response:
                    text = read_figma_response(response, lambda _text: None)
                calls = parse_client_tool_calls(text, tool_names)
                if calls:
                    tool_uses = [anthropic_tool_use(call) for call in calls]
                    for index, tool_use in enumerate(tool_uses):
                        for event, data in tool_use_stream_events(tool_use, index):
                            self.write_sse(event, data)
                        output_tokens += approximate_tokens(
                            json.dumps(tool_use["input"], ensure_ascii=False)
                        )
                    stop_reason = "tool_use"
                else:
                    text = client_visible_text(text)
                    self.write_sse(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        },
                    )
                    if text:
                        on_text(text)
                    self.write_sse(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": 0},
                    )
                    stop_reason = "end_turn"
            else:
                self.write_sse(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "text", "text": ""},
                    },
                )
                with call_figma(
                    prompt,
                    attachment_refs,
                    attachments,
                    request_template,
                ) as response:
                    read_figma_response(response, on_text)
                self.write_sse(
                    "content_block_stop",
                    {"type": "content_block_stop", "index": 0},
                )
                stop_reason = "end_turn"
        except UpstreamHTTPError as exc:
            self.write_sse(
                "error",
                {
                    "type": "error",
                    "error": {
                        "type": exc.error_type,
                        "message": str(exc),
                    },
                },
            )
            self.close_connection = True
            return
        except Exception as exc:
            self.write_sse(
                "error",
                {
                    "type": "error",
                    "error": {"type": "api_error", "message": str(exc)},
                },
            )
            self.close_connection = True
            return

        self.write_sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": output_tokens},
            },
        )
        self.write_sse("message_stop", {"type": "message_stop"})
        self.close_connection = True

    def handle_non_stream(
        self,
        prompt,
        model,
        tool_names,
        attachment_refs=None,
        attachments=None,
        request_template=None,
    ):
        with call_figma(
            prompt,
            attachment_refs,
            attachments,
            request_template,
        ) as response:
            text = read_figma_response(response, lambda _text: None)
        self.send_json(
            200,
            anthropic_response(
                text,
                model,
                approximate_tokens(prompt),
                tool_names,
            ),
        )


def main():
    config = validate_startup_config()
    host = getenv("FIGMA_ADAPTER_HOST", "127.0.0.1")
    port = config["port"]
    server = ThreadingHTTPServer((host, port), Handler)
    print(
        "figma anthropic adapter listening on %s:%s" % (host, port), flush=True
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
