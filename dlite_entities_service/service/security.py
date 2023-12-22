"""A security module for the Entities Service.

This module contains functions for authentication and authorization.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from dlite_entities_service.models.auth import TokenData, UserInBackend
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Literal

    from dlite_entities_service.service.backend.admin import AdminBackend

# to get a string like this run:
# openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="_auth/token")


def verify_password(
    plain_password: str | bytes, hashed_password: str | bytes | None
) -> bool:
    """Verify a password."""
    return PWD_CONTEXT.verify(plain_password, hashed_password)


def get_password_hash(password: str | bytes) -> str:
    """Get the hash of a password."""
    return PWD_CONTEXT.hash(password)


def get_user(username: str) -> UserInBackend | None:
    """Get a user from the admin backend."""
    backend = get_backend(CONFIG.admin_backend)

    if TYPE_CHECKING:  # pragma: no cover
        assert isinstance(backend, AdminBackend)  # nosec

    if (user_dict := backend.get_user(username)) is not None:
        return UserInBackend(**user_dict)
    return None


def authenticate_user(username: str, password: str) -> UserInBackend | Literal[False]:
    """Authenticate a user."""
    user = get_user(username)

    if not user:
        return False

    if not verify_password(password, user.hashed_password.get_secret_value()):
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
        raise TypeError("Set the private SSL key in the configuration.")

    return jwt.encode(
        to_encode, CONFIG.private_ssl_key.get_secret_value(), algorithm=ALGORITHM
    )


async def current_user(token: Annotated[str, Depends(OAUTH2_SCHEME)]) -> UserInBackend:
    """Verify a client user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if CONFIG.private_ssl_key is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_data = TokenData(
            **jwt.decode(
                token, CONFIG.private_ssl_key.get_secret_value(), algorithms=[ALGORITHM]
            )
        )
        if token_data.username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = get_user(username=token_data.username)

    if user is None:
        raise credentials_exception

    return user
