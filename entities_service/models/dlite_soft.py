"""DLite model."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, Field
from pydantic.networks import AnyHttpUrl


class DLiteProperty(BaseModel):
    """The defining metadata for a DLite Entity's property."""

    ref: Annotated[
        AnyHttpUrl | None,
        Field(
            validation_alias=AliasChoices("$ref", "ref"),
            serialization_alias="$ref",
            description=(
                "Formally a part of type. `$ref` is used together with the `ref` type, "
                "which is a special datatype for referring to other instances."
            ),
        ),
    ] = None


class DLiteEntity(BaseModel):
    """A DLite Entity."""

    meta: Annotated[
        Literal["http://onto-ns.com/meta/0.3/EntitySchema"],
        Field(
            description=(
                "URI for the metadata entity. For all entities at onto-ns.com, the "
                "EntitySchema v0.3 is used."
            ),
        ),
    ] = "http://onto-ns.com/meta/0.3/EntitySchema"
