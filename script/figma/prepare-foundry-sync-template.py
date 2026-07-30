#!/usr/bin/env python3

import argparse
import copy
import importlib.util
import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile


ADAPTER_PATH = pathlib.Path(__file__).with_name("anthropic-adapter.py")
MAX_CAPTURE_BYTES = 4 * 1024 * 1024
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
EXPECTED_BODY_KEYS = {
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


class PreparationError(ValueError):
    pass


def load_adapter():
    spec = importlib.util.spec_from_file_location(
        "figma_anthropic_adapter_sync_preparer",
        str(ADAPTER_PATH),
    )
    if spec is None or spec.loader is None:
        raise PreparationError("adapter could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Prepare a source-only Figma Foundry sync template.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Read the captured Foundry sync cURL from the macOS clipboard.",
    )
    parser.add_argument(
        "--allow-sensitive-input",
        action="store_true",
        help=(
            "Allow a local raw capture containing authentication headers; "
            "such headers are never written."
        ),
    )
    return parser.parse_args()


def read_capture(use_clipboard):
    if use_clipboard:
        value = subprocess.check_output(["pbpaste"])
    else:
        value = sys.stdin.buffer.read(MAX_CAPTURE_BYTES + 1)
    if len(value) > MAX_CAPTURE_BYTES:
        raise PreparationError("capture exceeds the 4 MiB safety limit")
    text = value.decode("utf-8", errors="replace")
    if not text.strip():
        raise PreparationError("capture is empty")
    return text


def captured_header_names(text):
    stripped = text.strip()
    if not stripped.startswith("curl"):
        return set()
    try:
        tokens = shlex.split(stripped.replace("\\\r\n", "").replace("\\\n", ""))
    except ValueError as exc:
        raise PreparationError("capture is not a valid cURL command") from exc
    names = set()
    index = 1
    while index < len(tokens):
        token = tokens[index]
        header = None
        if token in {"-H", "--header"}:
            index += 1
            if index >= len(tokens):
                raise PreparationError("capture is not a valid cURL command")
            header = tokens[index]
        elif token.startswith("--header="):
            header = token.split("=", 1)[1]
        elif token.startswith("-H") and token != "-H":
            header = token[2:]
        if isinstance(header, str) and ":" in header:
            names.add(header.split(":", 1)[0].strip().lower())
        index += 1
    return names


def source_change_is_safe(adapter, path, change, metadata_by_path):
    if (
        not adapter.valid_sync_path(path)
        or not isinstance(change, dict)
        or set(change) != {"entry", "type"}
        or change.get("type") != "upsert"
    ):
        return False
    entry = change.get("entry")
    return (
        isinstance(entry, dict)
        and set(entry) == {"contents", "metadata", "path"}
        and entry.get("path") == path
        and isinstance(entry.get("contents"), str)
        and adapter.valid_sync_entry_metadata(
            entry.get("metadata"),
            metadata_by_path.get(path),
        )
    )


def binary_change_is_removable(path, change):
    if (
        not isinstance(path, str)
        or not (
            path.startswith("src/imports/")
            or path.startswith("/src/imports/")
        )
        or not isinstance(change, dict)
        or set(change) != {"entry", "type"}
        or change.get("type") != "upsert"
    ):
        return False
    entry = change.get("entry")
    metadata = entry.get("metadata") if isinstance(entry, dict) else None
    return (
        isinstance(entry, dict)
        and set(entry) == {"downloadUrl", "metadata", "path"}
        and entry.get("path") == path
        and isinstance(entry.get("downloadUrl"), str)
        and isinstance(metadata, dict)
        and isinstance(metadata.get("blobRef"), str)
        and isinstance(metadata.get("mimeType"), str)
    )


def prepare_template(text, allow_sensitive_input=False):
    sensitive_headers = (
        captured_header_names(text) & SENSITIVE_HEADER_NAMES
    )
    if sensitive_headers and not allow_sensitive_input:
        raise PreparationError(
            "capture contains sensitive authentication headers; "
            "use --allow-sensitive-input only for local sanitization"
        )
    adapter = load_adapter()
    try:
        parsed = adapter.parse_figma_request_template(text)
    except ValueError as exc:
        raise PreparationError("capture is not valid JSON or cURL") from exc
    body = parsed["body"]
    if not isinstance(body, dict) or set(body) != EXPECTED_BODY_KEYS:
        raise PreparationError("capture has an unexpected Foundry sync shape")
    vfs = body.get("vfsChangeByPath")
    metadata_by_path = body.get("filePathToMetadata")
    if not isinstance(vfs, dict) or not isinstance(metadata_by_path, dict):
        raise PreparationError("capture has invalid Foundry sync files")

    safe_vfs = {}
    removed_paths = set()
    for path, change in vfs.items():
        if source_change_is_safe(adapter, path, change, metadata_by_path):
            safe_vfs[path] = copy.deepcopy(change)
        elif binary_change_is_removable(path, change):
            removed_paths.add(path)
        else:
            raise PreparationError(
                "capture contains an unreviewed Foundry sync entry at %s"
                % json.dumps(path, ensure_ascii=True)
            )

    safe_metadata = {}
    for path, metadata in metadata_by_path.items():
        if path in removed_paths:
            continue
        if not adapter.valid_sync_path(path) or not adapter.valid_sync_metadata(
            metadata
        ):
            raise PreparationError(
                "capture contains invalid Foundry sync metadata"
            )
        safe_metadata[path] = copy.deepcopy(metadata)
    if not set(safe_vfs).issubset(safe_metadata):
        raise PreparationError("capture has incomplete Foundry sync metadata")

    safe_body = copy.deepcopy(body)
    safe_body["vfsChangeByPath"] = safe_vfs
    safe_body["filePathToMetadata"] = safe_metadata
    document = {
        "format": adapter.FOUNDRY_SYNC_TEMPLATE_FORMAT,
        "body": safe_body,
        "headers": parsed["headers"],
    }
    structure_without_contents = copy.deepcopy(document)
    for change in structure_without_contents["body"][
        "vfsChangeByPath"
    ].values():
        change["entry"]["contents"] = ""
    if "\ufffd" in json.dumps(
        structure_without_contents,
        ensure_ascii=False,
    ):
        raise PreparationError(
            "capture contains invalid text outside reviewed source contents"
        )
    try:
        adapter.parse_foundry_sync_template(
            json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        )
    except ValueError as exc:
        raise PreparationError(
            "capture lacks a valid source-only Foundry sync snapshot: %s"
            % str(exc)
        ) from exc
    return document


def write_private_json(path_text, value):
    path = pathlib.Path(path_text)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".%s." % path.name,
        dir=str(path.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            handle.write("\n")
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
        write_private_json(
            arguments.output,
            prepare_template(
                read_capture(arguments.clipboard),
                allow_sensitive_input=arguments.allow_sensitive_input,
            ),
        )
    except (OSError, PreparationError) as exc:
        message = (
            str(exc)
            if isinstance(exc, PreparationError)
            else "capture or output could not be read"
        )
        print("error: %s" % message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
