"""SOFT5 model."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from entities_service.models.soft import SOFTEntity, SOFTProperty


class SOFT5Dimension(BaseModel):
    """The defining metadata for a SOFT5 Entity's dimension."""

    name: Annotated[str, Field(description="The name of the dimension.")]
    description: Annotated[
        str, Field(description="A human-readable description of the dimension.")
    ]


class SOFT5Property(SOFTProperty):
    """The defining metadata for a SOFT5 Entity's property."""

    name: Annotated[str, Field(description=("The name of the property."))]


class SOFT5Entity(SOFTEntity):
    """A SOFT5 Entity."""

    dimensions: Annotated[
        list[SOFT5Dimension],
        Field(
            description=(
                "A list of dimensions with name and an accompanying description."
            ),
        ),
    ] = []  # noqa: RUF012
    properties: Annotated[
        list[SOFT5Property], Field(description="A list of properties.")
    ]
