"""SOFT7 model."""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from entities_service.models.soft import SOFTEntity, SOFTProperty


class SOFT7Property(SOFTProperty):
    """The defining metadata for a SOFT7 Entity's property."""


class SOFT7Entity(SOFTEntity):
    """A SOFT7 Entity."""

    dimensions: Annotated[
        dict[str, str],
        Field(description="A dict of dimensions with an accompanying description."),
    ] = {}  # noqa: RUF012
    properties: Annotated[
        dict[str, SOFT7Property],
        Field(
            description=(
                "A dictionary of properties, mapping the property name to a dictionary "
                "of metadata defining the property."
            ),
        ),
    ]
