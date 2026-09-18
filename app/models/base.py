from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_cls: type[StrEnum], **kwargs) -> Mapped:
    """Column that stores a StrEnum's *values* as plain strings (portable; no native DB enum) and loads them back
    as enum members."""
    column_type = Enum(enum_cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])
    return mapped_column(column_type, **kwargs)
