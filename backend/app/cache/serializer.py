"""JSON serialization for cache values."""

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID


class CacheSerializer:
    """Serialize common application values to Redis-safe JSON strings."""

    @staticmethod
    def dumps(value: Any) -> str:
        return json.dumps(value, default=CacheSerializer._default, separators=(",", ":"))

    @staticmethod
    def loads(value: str | bytes) -> Any:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    @staticmethod
    def _default(value: Any) -> Any:
        if isinstance(value, (date, datetime, UUID)):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
