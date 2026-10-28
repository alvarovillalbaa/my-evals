"""Strict bounded JSON and canonical identities, without product execution."""

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile

from .errors import UserError

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 16 * 1024 * 1024


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise UserError("json_duplicate_key")
        result[key] = value
    return result


def _unicode(value):
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise UserError("json_invalid_unicode")
    elif isinstance(value, dict):
        for key, child in value.items():
            _unicode(key)
            _unicode(child)
    elif isinstance(value, list):
        for child in value:
            _unicode(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise UserError("json_nonfinite")


def read_bytes(path: Path, maximum: int = MAX_JSON_BYTES) -> bytes:
    """Read a bounded regular file; never follow a leaf link or wait on a FIFO."""
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise UserError("input_not_bounded_regular_file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise UserError("input_too_large")
        return data
    except OSError as error:
        raise UserError("input_unreadable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def parse_json(data: bytes, maximum: int = MAX_JSON_BYTES):
    if len(data) > maximum:
        raise UserError("input_too_large")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _value: (_ for _ in ()).throw(UserError("json_nonfinite")))
        _unicode(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as error:
        raise UserError("json_invalid") from error


def read_json(path: Path, maximum: int = MAX_JSON_BYTES):
    return parse_json(read_bytes(path, maximum), maximum)


def canonical(value) -> bytes:
    try:
        _unicode(value)
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise UserError("json_invalid") from error


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bytes(path: Path, data: bytes):
    """Publish a complete private file exclusively inside a user-selected directory."""
    temporary = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".personal-evals-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError as error:
        raise UserError("output_exists") from error
    except OSError as error:
        raise UserError("output_write_failed") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path: Path, value):
    data = canonical(value) + b"\n"
    if len(data) > MAX_REPORT_BYTES:
        raise UserError("output_too_large")
    write_bytes(path, data)
