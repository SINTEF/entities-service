"""Auth models."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
)


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


class GitLabUserInfo(BaseModel):
    """OpenID userinfo response from GitLab.

    This is defined in the OpenID Connect specification.
    Reference: https://openid.net/specs/openid-connect-core-1_0.html#UserInfo

    Claims not defined in the OpenID Connect specification are prefixed with
    `https://gitlab.org/claims/`.
    As well as the `groups` claim, which is a list of groups the user is a member of.
    """

    sub: Annotated[
        str, Field(description="Subject - Identifier for the End-User at the Issuer.")
    ]
    name: Annotated[
        str | None,
        Field(
            description=(
                "End-User's full name in displayable form including all name parts, "
                "possibly including titles and suffixes, ordered according to the "
                "End-User's locale and preferences."
            ),
        ),
    ] = None
    preferred_username: Annotated[
        str | None,
        Field(
            description=(
                "Shorthand name by which the End-User wishes to be referred to at the "
                "RP, such as `janedoe` or `j.doe`. This value MAY be any valid JSON "
                "string including special characters such as `@`, `/`, or whitespace. "
                "The RP MUST NOT rely upon this value being unique, as discussed in "
                "[Section 5.7](https://openid.net/specs/openid-connect-core-1_0.html"
                "#ClaimStability)."
            ),
        ),
    ] = None
    groups: Annotated[
        list[str],
        Field(
            description=(
                "Paths for the groups the user is a member of, either directly or "
                "through an ancestor group."
            ),
        ),
    ] = []
    groups_owner: Annotated[
        list[str],
        Field(
            alias="https://gitlab.org/claims/groups/owner",
            description=(
                "Names of the groups the user is a direct member of with Owner role."
            ),
        ),
    ] = []
    groups_maintainer: Annotated[
        list[str],
        Field(
            alias="https://gitlab.org/claims/groups/maintainer",
            description=(
                "Names of the groups the user is a direct member of with Maintainer "
                "role."
            ),
        ),
    ] = []
    groups_developer: Annotated[
        list[str],
        Field(
            alias="https://gitlab.org/claims/groups/developer",
            description=(
                "Names of the groups the user is a direct member of with Developer "
                "role."
            ),
        ),
    ] = []
