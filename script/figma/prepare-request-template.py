#!/usr/bin/env python3

import argparse
import copy
import importlib.util
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.parse


DEFAULT_MAX_PROJECT_FILES = 10
MAX_PROJECT_FILES = 64
MAX_CAPTURE_CHARACTERS = 4 * 1024 * 1024
MAX_INVALID_UTF8_SEQUENCES = 8
MAX_ATTACHMENT_CAPTURE_INVALID_UTF8_SEQUENCES = MAX_CAPTURE_CHARACTERS
MAX_REVIEWED_PROJECT_CAPTURE_INVALID_UTF8_SEQUENCES = (
    MAX_CAPTURE_CHARACTERS
)
ADAPTER_PATH = pathlib.Path(__file__).with_name("anthropic-adapter.py")
RUNTIME_CONFIG_KEYS = (
    "FIGMA_USER_ID",
    "FIGMA_FILE_KEY",
    "FIGMA_THREAD_ID",
    "FIGMA_ATTACHMENT_GUID",
    "FIGMA_FOUNDRY_ORIGIN_HOST",
)
SENSITIVE_HEADER_NAMES = {
    "api-key",
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
}
ATTACHMENT_RUNTIME_BODY_KEYS = {
    "agentId",
    "chatSdkEnabled",
    "codeLibraryFormat",
    "disableWebSearch",
    "featureType",
    "isKit",
    "isMobileClient",
    "makeStartedOnPlatform",
    "productType",
    "requestInitiator",
    "resumableMakeEnabled",
    "scopeKey",
    "scopeType",
    "startFileSeqNum",
    "supabaseEnabled",
    "todoAutoAccept",
}
ATTACHMENT_RUNTIME_STRING_KEYS = {
    "agentId",
    "featureType",
    "makeStartedOnPlatform",
    "productType",
    "requestInitiator",
    "scopeKey",
    "scopeType",
    "startFileSeqNum",
}
ATTACHMENT_RUNTIME_BOOL_KEYS = {
    "chatSdkEnabled",
    "disableWebSearch",
    "isKit",
    "isMobileClient",
    "resumableMakeEnabled",
    "supabaseEnabled",
    "todoAutoAccept",
}
ATTACHMENT_RUNTIME_INTEGER_KEYS = {"codeLibraryFormat"}
ATTACHMENT_RUNTIME_MESSAGE_KEYS = {
    "clientId",
    "guid",
    "supportRequestId",
    "userId",
}
SAFE_FS_SNAPSHOT_OPTIONS = {
    "path": "/tmp/sandbox",
    "listing": "recursive",
    "content": "snapshot",
    "ignorePatterns": [
        "node_modules",
        ".git",
        ".vite",
        "dist",
        ".cache",
        ".mcp.json",
    ],
    "respectGitignore": True,
}


class PreparationError(ValueError):
    pass


def load_adapter():
    spec = importlib.util.spec_from_file_location(
        "figma_anthropic_adapter_template_preparer",
        str(ADAPTER_PATH),
    )
    if spec is None or spec.loader is None:
        raise PreparationError("adapter could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Prepare a deployable Figma runtime request template.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--env-output")
    parser.add_argument(
        "--runtime-template-path",
        help=(
            "Path written to FIGMA_REQUEST_TEMPLATE_FILE in --env-output; "
            "defaults to the local --output path."
        ),
    )
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Read the capture from the macOS clipboard instead of stdin.",
    )
    parser.add_argument(
        "--allow-sensitive-input",
        action="store_true",
        help=(
            "Allow a local raw capture containing authentication headers; "
            "such headers are never written."
        ),
    )
    parser.add_argument(
        "--max-project-files",
        type=int,
        default=DEFAULT_MAX_PROJECT_FILES,
        help=(
            "Maximum reviewed non-binary project files to retain; "
            "defaults to 10 and cannot exceed 64."
        ),
    )
    parser.add_argument(
        "--attachment-runtime-only",
        action="store_true",
        help=(
            "Retain only the proven attachment request metadata, discard "
            "all project source files, and keep only the support-request header."
        ),
    )
    parser.add_argument(
        "--foundry-origin-host",
        help=(
            "Hostname captured from the matching Foundry sandbox request; "
            "written to FIGMA_FOUNDRY_ORIGIN_HOST in --env-output."
        ),
    )
    return parser.parse_args()


def bounded_capture(value):
    if not value or not value.strip():
        raise PreparationError("capture is empty")
    if len(value) > MAX_CAPTURE_CHARACTERS:
        raise PreparationError("capture exceeds the 4 MiB safety limit")
    return value


def decode_capture_bytes(
    value,
    max_invalid_utf8_sequences=MAX_INVALID_UTF8_SEQUENCES,
):
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        decoded = value.decode("utf-8", errors="replace")
        if decoded.count("\ufffd") > max_invalid_utf8_sequences:
            raise PreparationError(
                "clipboard contains too many invalid UTF-8 sequences"
            )
        return decoded


def read_capture_text(
    from_clipboard,
    max_invalid_utf8_sequences=MAX_INVALID_UTF8_SEQUENCES,
):
    if not from_clipboard:
        return bounded_capture(sys.stdin.read(MAX_CAPTURE_CHARACTERS + 1))
    try:
        process = subprocess.Popen(
            ["/usr/bin/pbpaste"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        stdout, unused_stderr = process.communicate()
    except OSError as exc:
        raise PreparationError("macOS clipboard could not be read") from exc
    if process.returncode != 0:
        raise PreparationError("macOS clipboard could not be read")
    return bounded_capture(
        decode_capture_bytes(stdout, max_invalid_utf8_sequences)
    )


def header_items(headers):
    if isinstance(headers, dict):
        return list(headers.items())
    if isinstance(headers, list):
        return headers
    return []


def capture_metadata(text):
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            value = json.loads(stripped)
        except ValueError as exc:
            raise PreparationError("capture is not valid JSON or cURL") from exc
        if not isinstance(value, dict):
            return {}, {}, set()
        headers = {}
        for item in header_items(value.get("headers")):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            name, header_value = item
            if isinstance(name, str) and isinstance(header_value, str):
                headers[name.strip().lower()] = header_value.strip()
        config = value.get("config")
        return (
            headers,
            config if isinstance(config, dict) else {},
            SENSITIVE_HEADER_NAMES.intersection(headers),
        )

    command = stripped.replace("\\\r\n", "").replace("\\\n", "")
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise PreparationError("capture is not valid JSON or cURL") from exc
    headers = {}
    sensitive_names = set()
    index = 1
    while index < len(tokens):
        token = tokens[index]
        captured_header = None
        if token in {"-H", "--header"}:
            index += 1
            if index >= len(tokens):
                raise PreparationError("capture is not valid JSON or cURL")
            captured_header = tokens[index]
        elif token.startswith("--header="):
            captured_header = token.split("=", 1)[1]
        elif token.startswith("-H") and token != "-H":
            captured_header = token[2:]
        if captured_header is not None:
            name, separator, header_value = captured_header.partition(":")
            if not separator:
                raise PreparationError("capture is not valid JSON or cURL")
            normalized_name = name.strip().lower()
            headers[normalized_name] = header_value.strip()
            if normalized_name in SENSITIVE_HEADER_NAMES:
                sensitive_names.add(normalized_name)
        elif token in {"-b", "--cookie", "-u", "--user"}:
            sensitive_names.add(
                "cookie" if token in {"-b", "--cookie"} else "authorization"
            )
            index += 1
            if index >= len(tokens):
                raise PreparationError("capture is not valid JSON or cURL")
        elif token.startswith("--cookie="):
            sensitive_names.add("cookie")
        elif token.startswith("--user="):
            sensitive_names.add("authorization")
        index += 1
    return headers, {}, sensitive_names


def is_binary_file(value):
    return isinstance(value, dict) and (
        value.get("type") == "binary"
        or "blobRef" in value
        or "mimeType" in value
    )


def sanitize_attachment_runtime_scalars(body):
    result = {}
    for key in ATTACHMENT_RUNTIME_BODY_KEYS:
        if key not in body:
            continue
        value = body[key]
        if key in ATTACHMENT_RUNTIME_STRING_KEYS:
            if (
                not isinstance(value, str)
                or not value
                or len(value) > 512
                or "\r" in value
                or "\n" in value
                or "\x00" in value
            ):
                raise PreparationError(
                    "attachment runtime metadata is invalid"
                )
        elif key in ATTACHMENT_RUNTIME_BOOL_KEYS:
            if not isinstance(value, bool):
                raise PreparationError(
                    "attachment runtime metadata is invalid"
                )
        elif key in ATTACHMENT_RUNTIME_INTEGER_KEYS:
            if isinstance(value, bool) or not isinstance(value, int):
                raise PreparationError(
                    "attachment runtime metadata is invalid"
                )
        result[key] = copy.deepcopy(value)
    return result


def sanitize_sboxd_url(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 4096
        or "\r" in value
        or "\n" in value
        or "\x00" in value
    ):
        raise PreparationError("attachment runtime URL is invalid")
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or not (hostname == "figma.com" or hostname.endswith(".figma.com"))
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise PreparationError("attachment runtime URL is invalid")
    return value


def validate_fs_snapshot_options(value):
    expected_keys = {
        "content",
        "ignorePatterns",
        "listing",
        "path",
        "respectGitignore",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise PreparationError(
            "attachment filesystem snapshot metadata is invalid"
        )
    for key in ("content", "listing", "path"):
        item = value[key]
        if (
            not isinstance(item, str)
            or not item
            or len(item) > 256
            or "\r" in item
            or "\n" in item
            or "\x00" in item
        ):
            raise PreparationError(
                "attachment filesystem snapshot metadata is invalid"
            )
    patterns = value["ignorePatterns"]
    if (
        not isinstance(patterns, list)
        or len(patterns) > 64
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > 256
            or "\r" in item
            or "\n" in item
            or "\x00" in item
            for item in patterns
        )
        or not isinstance(value["respectGitignore"], bool)
    ):
        raise PreparationError(
            "attachment filesystem snapshot metadata is invalid"
        )


def retained_invalid_text_paths(value, path=()):
    paths = []
    if isinstance(value, str):
        if "\ufffd" in value and not (
            len(path) == 3
            and path[0] == "body"
            and path[1] == "files"
        ):
            paths.append(path)
        return paths
    if isinstance(value, dict):
        for key, child in value.items():
            paths.extend(
                retained_invalid_text_paths(child, path + (str(key),))
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(
                retained_invalid_text_paths(child, path + (str(index),))
            )
    return paths


def derive_runtime_config(body, headers, captured_config):
    config = {}
    for key in RUNTIME_CONFIG_KEYS:
        value = captured_config.get(key)
        if isinstance(value, str) and value:
            config[key] = value

    if headers.get("x-figma-user-id"):
        config["FIGMA_USER_ID"] = headers["x-figma-user-id"]
    if headers.get("x-figma-file-key"):
        config["FIGMA_FILE_KEY"] = headers["x-figma-file-key"]
    thread_id = body.get("aiChatThreadId")
    if isinstance(thread_id, str) and thread_id:
        config["FIGMA_THREAD_ID"] = thread_id

    messages = body.get("aiChatMessages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            guid = message.get("guid")
            matched = (
                re.match(r"^([0-9]+):([0-9]+)$", guid)
                if isinstance(guid, str)
                else None
            )
            if matched:
                config["FIGMA_ATTACHMENT_GUID"] = "%s:%s" % (
                    matched.group(1),
                    int(matched.group(2)) + 1000000,
                )
            break

    for value in config.values():
        if "\r" in value or "\n" in value or "\x00" in value:
            raise PreparationError("runtime metadata contains invalid text")
    return config


def sanitize_file_metadata(value):
    if not isinstance(value, list):
        return []
    result = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        guid = entry.get("guid")
        version = entry.get("version")
        if (
            not isinstance(guid, str)
            or not guid
            or not isinstance(version, str)
            or not version
        ):
            continue
        result.append(
            {
                "guid": guid,
                "version": version,
            }
        )
    return result


def sanitize_body(
    body,
    max_project_files=DEFAULT_MAX_PROJECT_FILES,
    attachment_runtime_only=False,
):
    if (
        not isinstance(max_project_files, int)
        or max_project_files <= 0
        or max_project_files > MAX_PROJECT_FILES
    ):
        raise PreparationError(
            "max project files must be between 1 and 64"
        )
    sanitized = copy.deepcopy(body)

    files = sanitized.get("files")
    if not isinstance(files, dict):
        files = {}
    project_files = {
        path: value
        for path, value in files.items()
        if not is_binary_file(value)
    }
    if attachment_runtime_only:
        project_files = {}
    elif len(project_files) > max_project_files:
        raise PreparationError(
            "capture has more than %s non-binary project files"
            % max_project_files
        )
    sanitized["files"] = project_files
    if "fileMetadata" in sanitized:
        sanitized["fileMetadata"] = sanitize_file_metadata(
            sanitized["fileMetadata"]
        )
    sanitized["chats"] = []

    messages = sanitized.get("aiChatMessages")
    user_message = None
    if isinstance(messages, list):
        for candidate in reversed(messages):
            if isinstance(candidate, dict) and candidate.get("role") == "user":
                user_message = copy.deepcopy(candidate)
                break
    if user_message is not None:
        user_message["content"] = []
        for key in ("prompt", "rawPrompt", "text"):
            user_message.pop(key, None)
        sanitized["aiChatMessages"] = [user_message]
    else:
        sanitized["aiChatMessages"] = []

    raw_details = sanitized.get("rawUserChatDetails")
    if isinstance(raw_details, dict):
        raw_details["rawUserMessage"] = ""
        raw_details["attachments"] = []

    user_content = sanitized.get("userMessageContent")
    if isinstance(user_content, dict):
        user_content["plainText"] = ""
        user_content["imports"] = []

    for key in ("prompt", "rawPrompt", "rawUserMessage", "plainText"):
        if key in sanitized:
            sanitized[key] = ""
    if attachment_runtime_only:
        if user_message is None:
            raise PreparationError(
                "attachment runtime capture lacks a user message"
            )
        if "sboxdUrl" not in sanitized:
            raise PreparationError(
                "attachment runtime capture lacks a runtime URL"
            )
        if "fsSnapshotOptions" not in sanitized:
            raise PreparationError(
                "attachment runtime capture lacks filesystem metadata"
            )
        validate_fs_snapshot_options(sanitized["fsSnapshotOptions"])
        minimal = sanitize_attachment_runtime_scalars(sanitized)
        minimal["sboxdUrl"] = sanitize_sboxd_url(sanitized["sboxdUrl"])
        minimal["fsSnapshotOptions"] = copy.deepcopy(
            SAFE_FS_SNAPSHOT_OPTIONS
        )
        safe_user_message = {
            key: copy.deepcopy(user_message[key])
            for key in ATTACHMENT_RUNTIME_MESSAGE_KEYS
            if user_message is not None
            and isinstance(user_message.get(key), str)
            and user_message[key]
        }
        safe_user_message.update(
            {
                "role": "user",
                "content": [],
            }
        )
        minimal.update(
            {
                "aiChatMessages": [safe_user_message],
                "files": {},
                "fileMetadata": [],
                "chats": [],
                "rawUserChatDetails": {
                    "rawUserMessage": "",
                    "attachments": [],
                },
                "userMessageContent": {
                    "chatMode": "build",
                    "hidden": False,
                    "imports": [],
                    "libraryKeys": [],
                    "plainText": "",
                    "selectedNodeIds": [],
                },
                "chatCompression": {
                    "summary": "",
                    "totalSummarized": 0,
                },
                "serverSideCommitEnabled": False,
            }
        )
        return minimal
    return sanitized


def prepare_template(
    text,
    allow_sensitive_input=False,
    max_project_files=DEFAULT_MAX_PROJECT_FILES,
    attachment_runtime_only=False,
    foundry_origin_host=None,
):
    headers, captured_config, sensitive_names = capture_metadata(text)
    if sensitive_names and not allow_sensitive_input:
        raise PreparationError(
            "capture contains sensitive authentication headers; "
            "use --allow-sensitive-input only for a local sanitization step"
        )
    try:
        adapter = load_adapter()
        parsed = adapter.parse_figma_request_template(text)
    except (OSError, ValueError) as exc:
        raise PreparationError("capture is not valid JSON or cURL") from exc

    body = parsed["body"]
    prepared_headers = parsed["headers"]
    if attachment_runtime_only:
        prepared_headers = {
            name: value
            for name, value in prepared_headers.items()
            if name == "x-figma-support-request-id"
        }
    result = {
        "format": adapter.RUNTIME_TEMPLATE_FORMAT,
        "body": sanitize_body(
            body,
            max_project_files,
            attachment_runtime_only=attachment_runtime_only,
        ),
        "headers": prepared_headers,
    }
    if SENSITIVE_HEADER_NAMES.intersection(result["headers"]):
        raise PreparationError(
            "prepared template contains sensitive authentication headers"
        )
    if retained_invalid_text_paths(result):
        raise PreparationError(
            "retained runtime metadata contains invalid text"
        )
    config = derive_runtime_config(body, headers, captured_config)
    if foundry_origin_host is not None:
        if (
            len(foundry_origin_host) > 253
            or not re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",
                foundry_origin_host,
            )
            or not foundry_origin_host.lower().endswith(".figma.site")
        ):
            raise PreparationError(
                "Foundry origin host must be a figma.site hostname"
            )
        config["FIGMA_FOUNDRY_ORIGIN_HOST"] = foundry_origin_host
    if config:
        result["config"] = config
    try:
        adapter.parse_runtime_request_template(
            json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        )
    except ValueError as exc:
        raise PreparationError(
            "capture lacks required sanitized runtime structure"
        ) from exc
    return result


def write_private_json(path_text, value):
    text = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    write_private_text(path_text, text + "\n")


def env_fragment(template_path, config, runtime_template_path=None):
    configured_path = runtime_template_path or str(
        pathlib.Path(template_path).resolve()
    )
    if (
        "\r" in configured_path
        or "\n" in configured_path
        or "\x00" in configured_path
    ):
        raise PreparationError("runtime template path contains invalid text")
    values = {
        "FIGMA_REQUEST_TEMPLATE_FILE": configured_path,
    }
    values.update(config)
    return "".join(
        "%s=%s\n" % (key, json.dumps(values[key], ensure_ascii=False))
        for key in ("FIGMA_REQUEST_TEMPLATE_FILE",) + RUNTIME_CONFIG_KEYS
        if key in values
    )


def write_private_text(path_text, text):
    path = pathlib.Path(path_text)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".%s." % path.name,
        dir=str(path.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, str(path))
        temporary_path = None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


def main():
    arguments = parse_arguments()
    try:
        result = prepare_template(
            read_capture_text(
                arguments.clipboard,
                (
                    MAX_ATTACHMENT_CAPTURE_INVALID_UTF8_SEQUENCES
                    if arguments.attachment_runtime_only
                    else (
                        MAX_REVIEWED_PROJECT_CAPTURE_INVALID_UTF8_SEQUENCES
                        if arguments.max_project_files
                        > DEFAULT_MAX_PROJECT_FILES
                        else MAX_INVALID_UTF8_SEQUENCES
                    )
                ),
            ),
            allow_sensitive_input=arguments.allow_sensitive_input,
            max_project_files=arguments.max_project_files,
            attachment_runtime_only=arguments.attachment_runtime_only,
            foundry_origin_host=arguments.foundry_origin_host,
        )
        write_private_json(arguments.output, result)
        if arguments.env_output:
            write_private_text(
                arguments.env_output,
                env_fragment(
                    arguments.output,
                    result.get("config", {}),
                    arguments.runtime_template_path,
                ),
            )
    except PreparationError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except OSError:
        print("error: output file could not be written", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
