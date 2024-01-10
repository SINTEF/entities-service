"""A security module for the Entities Service.

This module contains functions for authentication and authorization.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt

from dlite_entities_service.models.auth import TokenData, UserInBackend
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.backend.mongodb import (
    MongoDBBackendWriteAccessError,
    discard_client_for_user,
    get_client,
)
from dlite_entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Literal

    from dlite_entities_service.service.backend.admin import AdminBackend

# to get a string like this run:
# openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="_auth/token")

LOGGER = logging.getLogger(__name__)


def verify_user(username: str, password: str) -> bool:
    """Verify a user, including credentials."""
    new_user_client = get_client(username=username, password=password)
    try:
        new_user_client[CONFIG.admin_db].command("ping")
    except MongoDBBackendWriteAccessError as exc:
        LOGGER.error("Could not verify user: username=%s", username)
        LOGGER.exception(exc)
        discard_client_for_user(username)
        return False

    return True


def get_user(username: str) -> UserInBackend | None:
    """Get a user from the admin backend."""
    backend: AdminBackend = get_backend(CONFIG.admin_backend)  # type: ignore[assignment]

    if (user_dict := backend.get_user(username)) is not None:
        return UserInBackend(**user_dict)
    return None


def authenticate_user(username: str, password: str) -> UserInBackend | Literal[False]:
    """Authenticate a user."""
    user = get_user(username)

    if not user:
        return False

    if not verify_user(user.username, password):
        return False

    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create an access token."""
    to_encode = data.copy()

    now = datetime.now(tz=timezone.utc)
    expire = now + expires_delta if expires_delta else now + timedelta(minutes=15)

    to_encode.update(
        {
            "iss": str(CONFIG.base_url),
            "exp": expire,
            "client_id": str(CONFIG.base_url),
            "iat": now,
        }
    )

    if CONFIG.private_ssl_key is None:
        raise ValueError("Set the private SSL key in the configuration.")

    return jwt.encode(
        to_encode, CONFIG.private_ssl_key.get_secret_value(), algorithm=ALGORITHM
    )


def get_token_data(token: str) -> TokenData:
    """Get token data."""
    if CONFIG.private_ssl_key is None:
        raise ValueError("Set the private SSL key in the configuration.")

    return TokenData(
        **jwt.decode(
            token,
            CONFIG.private_ssl_key.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=str(CONFIG.base_url),
        )
    )


async def current_user(token: Annotated[str, Depends(OAUTH2_SCHEME)]) -> UserInBackend:
    """Verify a client user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if CONFIG.private_ssl_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_data = get_token_data(token)
    except ExpiredSignatureError as exc:
        LOGGER.error("Token is expired: token=%s", token)
        LOGGER.exception(exc)
        credentials_exception.detail = "Token has expired. Please log in again."
        raise credentials_exception from exc
    except JWTError as exc:
        LOGGER.error("Could not validate token: token=%s", token)
        LOGGER.exception(exc)
        raise credentials_exception from exc

    # Validate token data that is not already validated through the JWT decoding
    if token_data.username is None or token_data.client_id != CONFIG.base_url:
        raise credentials_exception

    user = get_user(username=token_data.username)

    if user is None:
        raise credentials_exception

    return user
