#!/usr/bin/env python3

import argparse
import os
import pathlib
import re
import sys
import tempfile


ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
MUTABLE_KEYS = {
    "FIGMA_ADAPTER_HOST",
    "FIGMA_ADAPTER_PORT",
    "FIGMA_ATTACHMENT_GUID",
    "FIGMA_COOKIE_FILE",
    "FIGMA_FILE_KEY",
    "FIGMA_FOUNDRY_ORIGIN_HOST",
    "FIGMA_FOUNDRY_SYNC_TEMPLATE_FILE",
    "FIGMA_LOCK_TIMEOUT_SECONDS",
    "FIGMA_MAX_ATTACHMENT_BYTES",
    "FIGMA_MAX_REQUEST_BYTES",
    "FIGMA_REQUEST_TEMPLATE_FILE",
    "FIGMA_SELECTED_MODEL",
    "FIGMA_THREAD_ID",
    "FIGMA_TIMEOUT_SECONDS",
    "FIGMA_USER_ID",
}


class MergeError(ValueError):
    pass


def parse_env(path):
    order = []
    values = {}
    for raw_line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise MergeError("environment file contains an invalid line")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not ENV_NAME.fullmatch(name):
            raise MergeError("environment file contains an invalid name")
        if name not in values:
            order.append(name)
        values[name] = value
    return order, values


def unquoted_value(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_assignment(assignment):
    if "=" not in assignment:
        raise MergeError("--set requires NAME=VALUE")
    name, value = assignment.split("=", 1)
    if not ENV_NAME.fullmatch(name) or name not in MUTABLE_KEYS:
        raise MergeError("--set contains a disallowed name")
    if "\r" in value or "\n" in value or "\x00" in value:
        raise MergeError("--set contains invalid text")
    return name, value


def merge_environment(base_path, overlay_path=None, assignments=None):
    order, values = parse_env(base_path)
    if overlay_path:
        overlay_order, overlay_values = parse_env(overlay_path)
        for name in overlay_order:
            if name not in MUTABLE_KEYS:
                raise MergeError("overlay contains a disallowed name")
            if name not in values:
                order.append(name)
            values[name] = overlay_values[name]
    for assignment in assignments or []:
        name, value = parse_assignment(assignment)
        if name not in values:
            order.append(name)
        values[name] = value

    api_key = unquoted_value(values.get("FIGMA_ADAPTER_API_KEY", ""))
    if not api_key.strip():
        raise MergeError("base environment is missing FIGMA_ADAPTER_API_KEY")
    return "".join("%s=%s\n" % (name, values[name]) for name in order)


def atomic_private_write(path_text, text):
    path = pathlib.Path(path_text)
    existing_owner = None
    try:
        existing = path.stat()
        existing_owner = (existing.st_uid, existing.st_gid)
    except FileNotFoundError:
        pass
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".%s." % path.name,
        dir=str(path.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        if existing_owner is not None:
            os.fchown(descriptor, existing_owner[0], existing_owner[1])
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


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Safely merge non-secret Figma adapter runtime settings."
    )
    parser.add_argument("--base", required=True)
    parser.add_argument("--overlay")
    parser.add_argument("--output", required=True)
    parser.add_argument("--set", action="append", default=[])
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_args(argv or sys.argv[1:])
    try:
        merged = merge_environment(
            arguments.base,
            arguments.overlay,
            arguments.set,
        )
        atomic_private_write(arguments.output, merged)
    except (MergeError, OSError, UnicodeError):
        print("error: environment merge failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
