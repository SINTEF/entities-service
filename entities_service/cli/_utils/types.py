"""Reusable types and similar utilities for the CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple, Optional

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Enum with string values."""


from entities_service.models import Entity


class ValidEntity(NamedTuple):
    """A tuple containing a valid entity along with relevant information.

    `None` values mean "unknown" or "not applicable".
    """

    entity: Entity
    exists_remotely: bool | None
    equal_to_remote: bool | None
    pretty_diff: str | None


class EntityFileFormats(StrEnum):
    """Supported entity file formats."""

    JSON = "json"
    YAML = "yaml"
    YML = "yml"


class StrReversor(str):
    """Utility class to reverse the comparison of strings.

    Can be used to sort individual string parts of an interable in reverse order.

    Adapted from: https://stackoverflow.com/a/56842689/12404091
    """

    def __init__(self, obj: str) -> None:
        self.obj = obj

    def __hash__(self):
        return super().__hash__()

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, StrReversor):
            return super().__eq__(value)
        return value.obj == self.obj

    def __lt__(self, value: object, /) -> bool:
        """Reversed comparison."""
        if not isinstance(value, StrReversor):
            return super().__gt__(str(value))
        return value.obj < self.obj


# Type Aliases
OptionalBool = Optional[bool]
OptionalListEntityFileFormats = Optional[list[EntityFileFormats]]
OptionalListPath = Optional[list[Path]]
OptionalListStr = Optional[list[str]]
OptionalPath = Optional[Path]
OptionalStr = Optional[str]
