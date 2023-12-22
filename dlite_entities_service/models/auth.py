"""Auth models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    Field,
    SecretStr,
    ValidationInfo,
    field_validator,
)


class Token(BaseModel):
    """OAuth2 token."""

    access_token: Annotated[
        str,
        Field(
            description="The access token string as issued by the authorization server."
        ),
    ]
    token_type: Annotated[
        Literal["Bearer"],
        Field(description="The type of the token, typically just the string “Bearer”."),
    ] = "Bearer"


class TokenData(BaseModel):
    """Data stored in the JWT token."""

    username: Annotated[
        str | None,
        Field(
            description="Username of the user.",
            validation_alias=AliasChoices("sub", "username"),
        ),
    ] = None

    issuer: Annotated[
        AnyHttpUrl | None,
        Field(
            description="Issuer of the token. The authorization server identifier.",
            validation_alias=AliasChoices("iss", "issuer"),
        ),
    ] = None

    client_id: Annotated[
        AnyHttpUrl | None,
        Field(
            description="The client identifier.",
        ),
    ] = None

    issued_at: Annotated[
        datetime | None,
        Field(
            description="The time the token was issued.",
            validation_alias=AliasChoices("iat", "issued_at"),
        ),
    ] = None

    expires_at: Annotated[
        datetime | None,
        Field(
            description="The time the token will expire.",
            validation_alias=AliasChoices("exp", "expires_at"),
        ),
    ] = None

    @field_validator("issued_at", "expires_at", mode="before")
    @classmethod
    def _convert_to_datetime(
        cls, value: Any, info: ValidationInfo
    ) -> datetime | int | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, (float, int)):
            return datetime.fromtimestamp(value, tz=timezone.utc)

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass

        raise ValueError(f"Invalid value for {info.field_name}: {value}")


class User(BaseModel):
    """User model."""

    username: str
    full_name: str | None = None


class UserInBackend(User):
    """User model with hashed password."""

    hashed_password: SecretStr
