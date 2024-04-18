"""DLite Entity model based on the SOFT5 Entity model."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from entities_service.models.dlite_soft import DLiteEntity, DLiteProperty
from entities_service.models.soft5 import SOFT5Entity, SOFT5Property


class DLiteSOFT5Property(SOFT5Property, DLiteProperty):
    """The defining metadata for a (SOFT5-based) DLite Entity's property."""


class DLiteSOFT5Entity(SOFT5Entity, DLiteEntity):
    """A (SOFT5-based) DLite Entity."""

    properties: Annotated[  # type: ignore[assignment]
        list[DLiteSOFT5Property], Field(description="A list of properties.")
    ]
