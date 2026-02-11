from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

import orjson
import ulid

from jsonschemaform.config import KEY_PATTERN


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return now_utc()
    return now_utc()


def dumps_json(value: Any) -> str:
    return orjson.dumps(value).decode("utf-8")


def loads_json(value: str | None) -> Any:
    if not value:
        return None
    return orjson.loads(value)


def new_ulid() -> str:
    value = ulid.new()
    return getattr(value, "str", str(value))


def new_short_id() -> str:
    return secrets.token_urlsafe(8)


def generate_field_key(existing: set[str]) -> str:
    while True:
        candidate = f"f_{secrets.token_hex(6)}"
        if candidate not in existing and KEY_PATTERN.match(candidate):
            return candidate
