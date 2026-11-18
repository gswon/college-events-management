"""Opaque cursors for keyset pagination: on (start_at, id) for events, on (name, id) for organizations."""
import base64
import binascii
import json
from datetime import datetime

from errors import APIError


def encode_cursor(start_at: datetime, id_: int) -> str:
    raw = f"{start_at.isoformat()}|{id_}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        start_str, id_str = base64.urlsafe_b64decode(padded).decode().split("|")
        return datetime.fromisoformat(start_str), int(id_str)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise APIError(400, "INVALID_CURSOR", "Invalid cursor.")


def encode_name_cursor(name: str, id_: int) -> str:
    # JSON, because a name may contain any character, including "|".
    raw = json.dumps([name, id_]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_name_cursor(cursor: str) -> tuple[str, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        name, id_ = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(name, str) or not isinstance(id_, int):
            raise ValueError
        return name, id_
    except (binascii.Error, UnicodeDecodeError, ValueError, TypeError):
        raise APIError(400, "INVALID_CURSOR", "Invalid cursor.")
