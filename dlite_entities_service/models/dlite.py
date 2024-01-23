"""DLite model."""
from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic.networks import AnyHttpUrl

from dlite_entities_service.models.soft5 import SOFT5Entity, SOFT5Property
from dlite_entities_service.models.soft7 import SOFT7Entity, SOFT7Property


class DLiteSOFT5Property(SOFT5Property):
    """The defining metadata for a (SOFT5-based) DLite Entity's property."""

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


class DLiteSOFT5Entity(SOFT5Entity):
    """A (SOFT5-based) DLite Entity."""

    meta: Annotated[
        AnyHttpUrl,
        Field(
            description=(
                "URI for the metadata entity. For all entities at onto-ns.com, the "
                "EntitySchema v0.3 is used."
            ),
        ),
    ] = AnyHttpUrl("http://onto-ns.com/meta/0.3/EntitySchema")

    properties: Annotated[  # type: ignore[assignment]
        list[DLiteSOFT5Property], Field(description="A list of properties.")
    ]

    @field_validator("meta", mode="after")
    @classmethod
    def _only_support_onto_ns(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Validate `meta` only refers to onto-ns.com EntitySchema v0.3."""
        if str(value).rstrip("/") != "http://onto-ns.com/meta/0.3/EntitySchema":
            error_message = (
                "This service only works with DLite entities using EntitySchema "
                "v0.3 at onto-ns.com as the metadata entity.\n"
            )
            raise ValueError(error_message)
        return value


class DLiteSOFT7Property(SOFT7Property):
    """The defining metadata for a (SOFT7-based) DLite Entity's property."""

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


class DLiteSOFT7Entity(SOFT7Entity):
    """A (SOFT7-based) DLite Entity."""

    meta: Annotated[
        AnyHttpUrl,
        Field(
            description=(
                "URI for the metadata entity. For all entities at onto-ns.com, the "
                "EntitySchema v0.3 is used."
            ),
        ),
    ] = AnyHttpUrl("http://onto-ns.com/meta/0.3/EntitySchema")

    properties: Annotated[  # type: ignore[assignment]
        dict[str, DLiteSOFT7Property],
        Field(
            description=(
                "A dictionary of properties, mapping the property name to a dictionary "
                "of metadata defining the property."
            ),
        ),
    ]

    @field_validator("meta", mode="after")
    @classmethod
    def _only_support_onto_ns(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Validate `meta` only refers to onto-ns.com EntitySchema v0.3."""
        if str(value).rstrip("/") != "http://onto-ns.com/meta/0.3/EntitySchema":
            error_message = (
                "This service only works with DLite entities using EntitySchema "
                "v0.3 at onto-ns.com as the metadata entity.\n"
            )
            raise ValueError(error_message)
        return value


DLiteEntity = DLiteSOFT7Entity | DLiteSOFT5Entity
