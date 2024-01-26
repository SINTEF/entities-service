"""Auth models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    Field,
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


class Role(BaseModel):
    """MongoDB user role model."""

    role: str
    db: str


class UserInBackend(User):
    """User model with hashed password."""

    roles: list[Role]


class OpenIDConfiguration(BaseModel):
    """OpenID configuration for Code flow with PKCE."""

    issuer: AnyHttpUrl
    authorization_endpoint: AnyHttpUrl
    token_endpoint: AnyHttpUrl
    userinfo_endpoint: AnyHttpUrl | None = None
    jwks_uri: AnyHttpUrl
    registration_endpoint: AnyHttpUrl | None = None
    scopes_supported: list[str] | None = None
    response_types_supported: list[str]
    response_modes_supported: list[str] | None = None
    grant_types_supported: list[str] | None = None
    acr_values_supported: list[str] | None = None
    subject_types_supported: list[str]
    id_token_signing_alg_values_supported: list[str]
    id_token_encryption_alg_values_supported: list[str] | None = None
    id_token_encryption_enc_values_supported: list[str] | None = None
    userinfo_signing_alg_values_supported: list[str] | None = None
    userinfo_encryption_alg_values_supported: list[str] | None = None
    userinfo_encryption_enc_values_supported: list[str] | None = None
    request_object_signing_alg_values_supported: list[str] | None = None
    request_object_encryption_alg_values_supported: list[str] | None = None
    request_object_encryption_enc_values_supported: list[str] | None = None
    token_endpoint_auth_methods_supported: list[str] | None = None
    token_endpoint_auth_signing_alg_values_supported: list[str] | None = None
    display_values_supported: list[str] | None = None
    claim_types_supported: list[str] | None = None
    claims_supported: list[str] | None = None
    service_documentation: AnyHttpUrl | None = None
    claims_locales_supported: list[str] | None = None
    ui_locals_supported: list[str] | None = None
    claims_parameter_supported: bool = False
    request_parameter_supported: bool = False
    request_uri_parameter_supported: bool = True
    require_request_uri_registration: bool = False
    op_policy_uri: AnyHttpUrl | None = None
    op_tos_uri: AnyHttpUrl | None = None
    code_challenge_methods_supported: list[str]

    # Extras
    revocation_endpoint: AnyHttpUrl | None = None
    introspection_endpoint: AnyHttpUrl | None = None
