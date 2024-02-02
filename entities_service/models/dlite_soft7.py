"""DLite Entity model based on the SOFT7 Entity model."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from entities_service.models.dlite_soft import DLiteEntity, DLiteProperty
from entities_service.models.soft7 import SOFT7Entity, SOFT7Property


class DLiteSOFT7Property(SOFT7Property, DLiteProperty):
    """The defining metadata for a (SOFT7-based) DLite Entity's property."""


class DLiteSOFT7Entity(SOFT7Entity, DLiteEntity):
    """A (SOFT7-based) DLite Entity."""

    properties: Annotated[  # type: ignore[assignment]
        dict[str, DLiteSOFT7Property],
        Field(
            description=(
                "A dictionary of properties, mapping the property name to a dictionary "
                "of metadata defining the property."
            ),
        ),
    ]
