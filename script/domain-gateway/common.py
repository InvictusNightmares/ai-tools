"""Private configuration and output handling for domain operations."""

import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(__file__).resolve().parent / ".private"
DOMAIN = re.compile(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\Z")


class ConfigError(ValueError):
    pass


def load_private(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ConfigError("private configuration must be a regular file")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ConfigError("private configuration permissions must be 0600 or stricter")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        raise ConfigError("cannot read private JSON configuration") from None
    if not isinstance(data, dict):
        raise ConfigError("configuration must be a JSON object")
    return data


def domain(value):
    if not isinstance(value, str) or not DOMAIN.fullmatch(value):
        raise ConfigError("invalid domain name")
    return value


def text(value, field):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ConfigError(f"invalid text field: {field}")
    if "<" in value or ">" in value or "{{" in value:
        raise ConfigError(f"replace placeholder field: {field}")
    return value


def absolute_path(value, field):
    value = text(value, field)
    if not Path(value).is_absolute():
        raise ConfigError(f"absolute path required: {field}")
    return value


def private_output(path):
    path = Path(path).absolute()
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT) and not resolved.is_relative_to(PRIVATE):
        raise ConfigError("generated private files must be outside tracked project directories")
    if path.is_symlink():
        raise ConfigError("output must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def write_new_private(path, content):
    path = private_output(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)


def append_log(path):
    path = private_output(path)
    if path.exists() and (not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077):
        raise ConfigError("existing log must be a private regular file")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(path, flags, 0o600), "ab")
