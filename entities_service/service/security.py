"""A security module for the Entities Service.

This module contains functions for authentication and authorization.
"""

from __future__ import annotations

import logging
from json import JSONDecodeError
from typing import Annotated
from urllib.parse import quote_plus

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from httpx import AsyncClient, HTTPError
from pydantic import ValidationError

from entities_service.models.auth import (
    GitLabGroupProjectMember,
    GitLabOpenIDUserInfo,
    GitLabRole,
    GitLabUser,
    OpenIDConfiguration,
)
from entities_service.service.config import CONFIG

# to get a string like this run:
# openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

SECURITY_SCHEME = HTTPBearer()

LOGGER = logging.getLogger(__name__)


async def get_openid_config() -> OpenIDConfiguration:
    """Get the OpenID configuration."""
    async with AsyncClient() as client:
        try:
            response = await client.get(
                f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}"
                "/.well-known/openid-configuration"
            )
        except HTTPError as exc:
            raise ValueError("Could not get OpenID configuration.") from exc

    try:
        return OpenIDConfiguration(**response.json())
    except (JSONDecodeError, ValidationError) as exc:
        raise ValueError("Could not parse OpenID configuration.") from exc


async def verify_user_access_token(token: str) -> tuple[bool, int | None, str | None]:
    """Verify a user-provided GitLab access token."""
    # Get current user
    async with AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client:
        try:
            response = await client.get(
                f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user"
            )
        except HTTPError as exc:
            LOGGER.error("Could not get user info from GitLab provider.")
            LOGGER.exception(exc)
            return False, None, None

    try:
        user = GitLabUser(**response.json())
    except (JSONDecodeError, ValidationError) as exc:
        LOGGER.error("Could not parse user info from GitLab provider.")
        LOGGER.error("Response:\n%s", response.text)
        LOGGER.exception(exc)
        return False, None, None

    # Check user validity
    if user.state != "active" or user.locked:
        LOGGER.error("User is not active or is locked.")
        return (
            False,
            status.HTTP_403_FORBIDDEN,
            (
                "Your user account is not active or is locked. "
                "Please contact your GitLab administrator(s)."
            ),
        )

    # Check if user is a member of the roles group
    async with AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client:
        try:
            response = await client.get(
                f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4"
                f"/groups/{quote_plus(CONFIG.roles_group)}/members/{user.id}",
            )
        except HTTPError as exc:
            LOGGER.error("User is not a member of the entities-service group.")
            LOGGER.exception(exc)
            return (
                False,
                status.HTTP_403_FORBIDDEN,
                (
                    "You are not a member of the entities-service group. "
                    "Please contact the entities-service group maintainer."
                ),
            )

    # Check if user has the rights to create entities
    try:
        member = GitLabGroupProjectMember(**response.json())
    except (JSONDecodeError, ValidationError) as exc:
        LOGGER.error("Could not parse member role from GitLab provider.")
        LOGGER.error("Response:\n%s", response.text)
        LOGGER.exception(exc)
        return False, None, None

    # Sanity checks
    if any(
        getattr(member, identifier) != getattr(user, identifier)
        for identifier in ("id", "username", "name", "state")
    ):
        LOGGER.error("Member info does not match the user info.")
        return False, None, None

    if member.access_level < GitLabRole.DEVELOPER:
        LOGGER.error(
            "User does not have the rights to create entities. "
            "Hint: Change %s's role in the GitLab group %r",
            member.username,
            CONFIG.roles_group,
        )
        return (
            False,
            status.HTTP_403_FORBIDDEN,
            (
                "You do not have the rights to create entities. "
                "Please contact the entities-service group maintainer."
            ),
        )

    LOGGER.debug(
        "User %s (%s, %s) has the rights to create entities.",
        member.name,
        member.id,
        member.username,
    )

    LOGGER.info("User: %s", member.name)

    return True, None, None


async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(SECURITY_SCHEME)]
) -> None:
    """Verify a client user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials.credentials:
        raise credentials_exception

    # Retrieve the OpenID configuration for the OAuth2 provider
    try:
        openid_config = await get_openid_config()
    except ValueError as exc:
        LOGGER.error("Could not get OpenID configuration.")
        LOGGER.exception(exc)
        raise credentials_exception from exc

    if openid_config.userinfo_endpoint is None:
        LOGGER.error("OpenID configuration does not contain a userinfo endpoint.")
        raise credentials_exception

    # Get the user info from the OAuth2 provider based on the current credentials
    async with AsyncClient() as client:
        try:
            response = await client.get(
                str(openid_config.userinfo_endpoint),
                headers={
                    "Authorization": f"{credentials.scheme} {credentials.credentials}"
                },
            )
        except HTTPError as exc:
            LOGGER.error("Could not get user info from OAuth2 provider.")
            LOGGER.exception(exc)
            raise credentials_exception from exc

    try:
        userinfo = GitLabOpenIDUserInfo(**response.json())
    except (JSONDecodeError, ValidationError) as exc:
        LOGGER.error("Could not parse user info from OAuth2 provider.")
        LOGGER.error("Response:\n%s", response.text)

        # If this fails, it may be that we are dealing with a user-provided access token
        verified, status_code, error_msg = await verify_user_access_token(
            credentials.credentials
        )

        if verified:
            return

        if status_code is not None:
            credentials_exception.status_code = status_code

        if error_msg is not None:
            credentials_exception.detail = error_msg

        LOGGER.exception(exc)
        raise credentials_exception from exc

    if CONFIG.roles_group not in userinfo.groups:
        LOGGER.error("User is not a member of the entities-service group.")
        credentials_exception.status_code = status.HTTP_403_FORBIDDEN
        credentials_exception.detail = (
            "You are not a member of the entities-service group. "
            "Please contact the entities-service group maintainer."
        )
        raise credentials_exception

    if not any(
        CONFIG.roles_group in group
        for group in [
            userinfo.groups_owner,
            userinfo.groups_maintainer,
            userinfo.groups_developer,
        ]
    ):
        LOGGER.error(
            "User does not have the rights to create entities. "
            "Hint: Change %s's role in the GitLab group %r",
            userinfo.preferred_username,
            CONFIG.roles_group,
        )
        credentials_exception.status_code = status.HTTP_403_FORBIDDEN
        credentials_exception.detail = (
            "You do not have the rights to create entities. "
            "Please contact the entities-service group maintainer."
        )
        raise credentials_exception

    LOGGER.info("User: %s", userinfo.preferred_username)
