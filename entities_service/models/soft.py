"""Base (minimum set) models for SOFT entities."""

from __future__ import annotations

import difflib
import re
from typing import Annotated, Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.networks import AnyHttpUrl

from entities_service.service.config import CONFIG

URI_REGEX = re.compile(
    r"^(?P<namespace>https?://.+)/(?P<version>\d(?:\.\d+){0,2})/(?P<name>[^/#?]+)$"
)
"""Regular expression to parse a SOFT entity URI."""


class SOFTProperty(BaseModel):
    """The minimum set of defining metadata for a SOFT Entity's property."""

    model_config = ConfigDict(extra="forbid")

    type_: Annotated[
        str,
        Field(
            alias="type",
            description="The type of the described property, e.g., an integer.",
        ),
    ]
    shape: Annotated[
        list[str] | None,
        Field(
            description=(
                "The dimension of multi-dimensional properties. This is a list of "
                "dimension expressions referring to the dimensions defined above. For "
                "instance, if an entity have dimensions with names `H`, `K`, and `L` "
                "and a property with shape `['K', 'H+1']`, the property of an instance "
                "of this entity with dimension values `H=2`, `K=2`, `L=6` will have "
                "shape `[2, 3]`."
            ),
            validation_alias=AliasChoices("dims", "shape"),
        ),
    ] = None
    unit: Annotated[str | None, Field(description="The unit of the property.")] = None
    description: Annotated[
        str, Field(description="A human-readable description of the property.")
    ]


class SOFTEntity(BaseModel):
    """A minimum Field set SOFT Entity to be used in a versioned SOFT Entity model."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(description="The name of the entity.")] = None
    version: Annotated[str | None, Field(description="The version of the entity.")] = (
        None
    )
    namespace: Annotated[
        AnyHttpUrl | None, Field(description="The namespace of the entity.")
    ] = None
    uri: Annotated[
        AnyHttpUrl | None,
        Field(
            description=(
                "The universal identifier for the entity. This MUST start with the base"
                " URL."
            ),
        ),
    ] = None
    description: Annotated[str, Field(description="Description of the entity.")] = ""

    @field_validator("uri", "namespace", mode="after")
    @classmethod
    def _validate_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Validate `uri` and `namespace` starts with the current base URL for the
        service."""
        if not str(value).startswith(str(CONFIG.base_url)):
            error_message = (
                "This service only works with SOFT entities at " f"{CONFIG.base_url}.\n"
            )
            raise ValueError(error_message)
        return value

    @field_validator("uri", mode="after")
    @classmethod
    def _validate_uri(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Validate `uri` is consistent with `name`, `version`, and `namespace`."""
        if URI_REGEX.match(str(value)) is None:
            error_message = (
                "The 'uri' is not a valid SOFT7 entity URI. It must be of the form "
                f"{str(CONFIG.base_url).rstrip('/')}/{{version}}/{{name}}.\n"
            )
            raise ValueError(error_message)
        return value

    @model_validator(mode="before")
    @classmethod
    def _check_cross_dependent_fields(cls, data: Any) -> Any:
        """Check that `name`, `version`, and `namespace` are all set or all unset."""
        if (
            isinstance(data, dict)
            and any(data.get(_) is None for _ in ("name", "version", "namespace"))
            and not all(data.get(_) is None for _ in ("name", "version", "namespace"))
        ):
            error_message = (
                "Either all of `name`, `version`, and `namespace` must be set "
                "or all must be unset.\n"
            )
            raise ValueError(error_message)

        if (
            isinstance(data, dict)
            and any(data.get(_) is None for _ in ("name", "version", "namespace"))
            and data.get("uri") is None
        ):
            error_message = (
                "Either `name`, `version`, and `namespace` or `uri` must be set.\n"
            )
            raise ValueError(error_message)

        if (
            isinstance(data, dict)
            and all(data.get(_) is not None for _ in ("name", "version", "namespace"))
            and data.get("uri") is not None
            and data["uri"] != f"{data['namespace']}/{data['version']}/{data['name']}"
        ):
            # Ensure that `uri` is consistent with `name`, `version`, and `namespace`.
            diff = "\n  ".join(
                difflib.ndiff(
                    [data["uri"]],
                    [f"{data['namespace']}/{data['version']}/{data['name']}"],
                )
            )
            error_message = (
                "The `uri` is not consistent with `name`, `version`, and "
                f"`namespace`:\n\n  {diff}\n\n"
            )
            raise ValueError(error_message)
        return data
