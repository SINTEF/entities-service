"""Base (minimum set) models for SOFT entities."""

from __future__ import annotations

import difflib
import re
from typing import Annotated, Any
from urllib.parse import quote

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic.functional_validators import AfterValidator
from pydantic.networks import AnyHttpUrl

from entities_service.service.config import CONFIG

SEMVER_REGEX = (
    r"(?P<major>0|[1-9]\d*)(?:\.(?P<minor>0|[1-9]\d*))?(?:\.(?P<patch>0|[1-9]\d*))?"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
"""Semantic Versioning regular expression.

Slightly changed version of the one found at https://semver.org.
The changed bits pertain to `minor` and `patch`, which are now both optional.
"""

NO_GROUPS_SEMVER_REGEX = (
    r"(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))?(?:\.(?:0|[1-9]\d*))?"
    r"(?:-(?:(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?:[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
"""Semantic Versioning regular expression.

Slightly changed version of the one found at https://semver.org.
The changed bits pertain to `minor` and `patch`, which are now both optional.

This is the same as `SEMVER_REGEX`, but without the named groups.
"""

URI_REGEX = re.compile(
    rf"^(?P<namespace>https?://.+)/(?P<version>{NO_GROUPS_SEMVER_REGEX})/(?P<name>[^/#?]+)$"
)
"""Regular expression to parse a SOFT entity URI."""


def _disallowed_characters(value: str) -> str:
    """Check that the value does not contain disallowed characters."""
    special_url_characters = ["/", "?", "#", "@", ":"]
    if any(char in value for char in special_url_characters):
        raise ValueError(
            f"The value must not contain any of {special_url_characters} characters."
        )
    if " " in value:
        raise ValueError("The value must not contain any spaces.")
    return value


def _ensure_url_encodeable(value: str) -> str:
    """Ensure that the value is URL encodeable."""
    try:
        quote(value)
    except Exception as error:  # noqa: BLE001
        raise ValueError(f"The value is not URL encodeable: {error}") from error
    return value


EntityVersionType = Annotated[
    str,
    Field(description="The version of the entity.", pattern=rf"^{SEMVER_REGEX}$"),
]
EntityNameType = Annotated[
    str,
    Field(description="The name of the entity."),
    AfterValidator(_disallowed_characters),
    AfterValidator(_ensure_url_encodeable),
]


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

    name: EntityNameType | None = None
    version: EntityVersionType | None = None
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
                f"This service only works with SOFT entities at {CONFIG.base_url}.\n"
            )
            raise ValueError(error_message)
        return value

    @field_validator("uri", mode="after")
    @classmethod
    def _validate_uri(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Validate all parts of the `uri`."""
        try:
            uri_deconstructed = URI_REGEX.match(str(value))
        except Exception as error:  # noqa: BLE001
            error_message = f"The URI is invalid: {error}\n"
            raise ValueError(error_message) from error

        if uri_deconstructed is None:
            error_message = (
                "The URI does not match the expected pattern. The URI must be of the "
                "form `{namespace}/{version}/{name}`.\n"
            )
            raise ValueError(error_message)

        try:
            TypeAdapter(EntityNameType).validate_python(uri_deconstructed.group("name"))
        except (ValueError, ValidationError) as error:
            error_message = f"The name part of the URI is invalid: {error}\n"
            raise ValueError(error_message) from error

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
