"""(start_at, id) keyset 페이지네이션용 opaque cursor."""
import base64
import binascii
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
        raise APIError(400, "INVALID_CURSOR", "cursor 값이 올바르지 않습니다.")
