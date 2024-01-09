"""Service app configuration."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, SecretBytes, SecretStr, field_validator
from pydantic.networks import AnyHttpUrl, MultiHostUrl, UrlConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

from dlite_entities_service.service.backend import Backends

MongoDsn = Annotated[
    MultiHostUrl, UrlConstraints(allowed_schemes=["mongodb", "mongodb+srv"])
]
"""Support MongoDB schemes with hidden port (no default port)."""


class ServiceSettings(BaseSettings):
    """Service app configuration."""

    model_config = SettingsConfigDict(
        env_prefix="entity_service_", env_file=".env", extra="ignore"
    )

    debug: Annotated[
        bool,
        Field(
            description="Enable debug mode.",
        ),
    ] = False

    base_url: Annotated[
        AnyHttpUrl,
        Field(
            description="Base URL, where the service is running.",
        ),
    ] = AnyHttpUrl("http://onto-ns.com/meta")

    backend: Annotated[
        Backends,
        Field(
            description="Backend to use for storing entities.",
        ),
    ] = Backends.MONGODB

    private_ssl_key: Annotated[
        SecretStr | SecretBytes | None, Field(description="The loaded private SSL key.")
    ] = None

    # MongoDB settings
    mongo_uri: Annotated[
        MongoDsn,
        Field(
            description="URI for the MongoDB cluster/server.",
        ),
    ] = MongoDsn("mongodb://localhost:27017")

    mongo_user: Annotated[
        str, Field(description="Username for connecting to the MongoDB.")
    ] = "guest"

    mongo_password: Annotated[
        SecretStr | SecretBytes,
        Field(description="Password for connecting to the MongoDB."),
    ] = SecretStr("guest")

    mongo_db: Annotated[
        str,
        Field(
            description=(
                "Name of the MongoDB database for storing entities in the Entities "
                "Service."
            ),
        ),
    ] = "entities_service"

    mongo_collection: Annotated[
        str,
        Field(
            description="Name of the MongoDB collection for storing entities.",
        ),
    ] = "entities"

    # Special admin DB settings for the Entities Service
    # We will use the same MongoDB cluster/server for the admin DB
    # as for the entities DB, but we will use a different database.
    admin_backend: Annotated[
        Literal[Backends.ADMIN],
        Field(
            description="Backend to use for storing admin data.",
        ),
    ] = Backends.ADMIN

    admin_user: Annotated[
        SecretStr | SecretBytes | None,
        Field(
            description=(
                "Admin username for connecting to the Entities Service's admin DB."
            ),
        ),
    ] = None

    admin_password: Annotated[
        SecretStr | SecretBytes | None,
        Field(
            description=(
                "Admin password for connecting to the Entities Service's admin DB."
            ),
        ),
    ] = None

    admin_db: Annotated[
        str,
        Field(
            description=(
                "Name of the MongoDB database for storing admin collections used in "
                "the Entities Service."
            ),
        ),
    ] = "admin"

    @field_validator("base_url", mode="before")
    @classmethod
    def _strip_ending_slashes(cls, value: Any) -> AnyHttpUrl:
        """Strip any end forward slashes."""
        return AnyHttpUrl(str(value).rstrip("/"))


CONFIG = ServiceSettings()
