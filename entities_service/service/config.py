"""Service app configuration."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic.networks import AnyHttpUrl, UrlConstraints
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from entities_service.service.backend import Backends

MongoDsn = Annotated[
    MultiHostUrl, UrlConstraints(allowed_schemes=["mongodb", "mongodb+srv"])
]
"""Support MongoDB schemes with hidden port (no default port)."""


class OAuth2Provider(Enum):
    """Enumeration of supported OAuth2 providers."""

    GITLAB = "gitlab"


class ServiceSettings(BaseSettings):
    """Service app configuration."""

    model_config = SettingsConfigDict(
        env_prefix="entities_service_", env_file=".env", extra="ignore"
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

    # Security
    oauth2_provider: Annotated[
        OAuth2Provider,
        Field(
            description="OAuth2 provider. (Currently only GitLab is supported.)",
        ),
    ] = OAuth2Provider.GITLAB

    oauth2_provider_base_url: Annotated[
        AnyHttpUrl, Field(description="OAuth2 provider base URL.")
    ] = AnyHttpUrl("https://gitlab.sintef.no")

    access_token: Annotated[
        SecretStr | None, Field(description="Access token for the OAuth2 provider.")
    ] = None

    roles_group: Annotated[str, Field(description="GitLab group for roles.")] = (
        "team4.0-authentication/entities-service"
    )

    # MongoDB backend settings
    mongo_uri: Annotated[
        MongoDsn,
        Field(
            description="URI for the MongoDB cluster/server.",
        ),
    ] = MongoDsn("mongodb://localhost:27017")

    mongo_user: Annotated[
        str,
        Field(
            description="Username for connecting to the MongoDB with read-only rights."
        ),
    ] = "guest"

    mongo_password: Annotated[
        SecretStr,
        Field(
            description="Password for connecting to the MongoDB with read-only rights."
        ),
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

    x509_certificate_file: Annotated[
        Path | None,
        Field(
            description=(
                "File path to a X.509 certificate for connecting to the MongoDB "
                "backend with write-access rights."
            ),
        ),
    ] = None

    ca_file: Annotated[
        Path | None,
        Field(
            description=(
                "File path to a CA certificate for connecting to the MongoDB backend "
                "with write-access rights."
            ),
        ),
    ] = None

    @field_validator("base_url", mode="before")
    @classmethod
    def _strip_ending_slashes(cls, value: Any) -> AnyHttpUrl:
        """Strip any end forward slashes."""
        return AnyHttpUrl(str(value).rstrip("/"))

    @field_validator("x509_certificate_file", "ca_file", mode="before")
    @classmethod
    def _handle_raw_certificate(cls, value: Any, info: ValidationInfo) -> Any:
        """Handle the case of the value being a "raw" certificate file content."""
        cache_dir = Path.home() / ".cache" / "entities-service"
        if not info.field_name:
            raise ValueError(
                "This validator can only be used for fields with a name, "
                "i.e. not for root fields."
            )
        cache_file_name = info.field_name.replace("_file", "")
        cache_file = cache_dir / f"{cache_file_name}.pem"

        if isinstance(value, bytes):
            # Expect it to not be a path, but a "raw" certificate file content
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(value)  # Will overwrite existing file
            cache_file.chmod(0o600)
            return cache_file

        if isinstance(value, str):
            value_as_path = Path(value)
            try:
                if value_as_path.exists() and value_as_path.is_file():
                    return value_as_path
            except OSError:
                pass

            # Expect the value to be a "raw" certificate file content
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(value)  # Will overwrite existing file
            cache_file.chmod(0o600)
            return cache_file

        return value

    @field_validator("x509_certificate_file", "ca_file", mode="after")
    @classmethod
    def _ensure_is_existing_file(cls, value: Path | None) -> Path | None:
        """Ensure the certificate file exists."""
        if value is None:
            # No certificate file provided
            return value

        if not value.exists():
            raise FileNotFoundError(f"Certificate file {value} does not exist")

        if not value.is_file():
            raise FileNotFoundError(f"Certificate file {value} is not a file")

        return value


CONFIG = ServiceSettings()
