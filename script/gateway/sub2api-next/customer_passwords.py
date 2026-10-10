"""Read operator-provided customer passwords without deriving or changing them.

Keep the JSON object mapping login emails to passwords outside the repository.
The default is /opt/sub2api-next/ops/customer-passwords.json; callers may pass an
absolute path or set SUB2API_CUSTOMER_PASSWORDS_FILE. Only the current operator
may own or access the regular file. This module never writes credential files.
"""
import json
import os
from pathlib import Path
import stat


DEFAULT_PATH = '/opt/sub2api-next/ops/customer-passwords.json'
PATH_ENV = 'SUB2API_CUSTOMER_PASSWORDS_FILE'
MAX_BYTES = 1024 * 1024


class CustomerPasswordError(RuntimeError):
    """An operator must supply or repair the private password file."""


def _fail(message):
    raise CustomerPasswordError('customer password file ' + message) from None


def _check_stat(info):
    if not stat.S_ISREG(info.st_mode):
        _fail('must be a regular file')
    if info.st_uid != os.geteuid():
        _fail('must be owned by this operator')
    if info.st_mode & 0o077:
        _fail('must not grant group or other permissions')
    if info.st_size > MAX_BYTES:
        _fail('exceeds the size limit')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('contains duplicate entries')
        result[key] = value
    return result


def customer_password(email, path=None):
    """Return one supplied password; fail closed without a password fallback."""
    selected = path if path is not None else os.environ.get(PATH_ENV, DEFAULT_PATH)
    if not isinstance(selected, (str, Path)) or not str(selected):
        _fail('requires an absolute path')
    source = Path(selected)
    if not source.is_absolute():
        _fail('requires an absolute path')
    try:
        # Reject redirected parent directories as well as a symlink at the leaf.
        if source.resolve() != source or source.is_symlink():
            _fail('must not use symlinks or redirected paths')
        before = source.lstat()
        _check_stat(before)
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
        with os.fdopen(os.open(str(source), flags), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            _check_stat(opened)
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                _fail('changed while being opened')
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            _check_stat(after)
            if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                _fail('changed while being read')
    except CustomerPasswordError:
        raise
    except FileNotFoundError:
        _fail('is missing; supply it before explicit customer login or creation')
    except (OSError, ValueError, RuntimeError):
        _fail('cannot be read safely')
    if len(raw) > MAX_BYTES:
        _fail('exceeds the size limit')
    try:
        passwords = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
    except CustomerPasswordError:
        raise
    except (UnicodeError, ValueError):
        _fail('must contain valid UTF-8 JSON')
    if not isinstance(passwords, dict):
        _fail('must contain an email-to-password object')
    for login_email, password in passwords.items():
        if (not isinstance(login_email, str) or '@' not in login_email
                or any(character.isspace() for character in login_email)
                or not isinstance(password, str)):
            _fail('contains an invalid email-to-password entry')
        if len(password) < 6:
            _fail('contains a password shorter than six characters')
    if not isinstance(email, str) or email not in passwords:
        _fail('has no entry for the requested customer')
    return passwords[email]
