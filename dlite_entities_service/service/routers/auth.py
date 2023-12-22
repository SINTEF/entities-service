"""Authentication module for the Entities Service."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from dlite_entities_service.models.auth import NewUser, Token, User
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.config import CONFIG
from dlite_entities_service.service.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
)

if TYPE_CHECKING:  # pragma: no cover
    from dlite_entities_service.service.backend.admin import (
        AdminBackend,
        BackendUserDict,
    )

ROUTER = APIRouter(prefix="/_auth", include_in_schema=False)


@ROUTER.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    internal_server_error = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user = authenticate_user(form_data.username, form_data.password)
    except TypeError as exc:
        raise internal_server_error from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    try:
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
    except TypeError as exc:
        raise internal_server_error from exc

    return {"access_token": access_token}


@ROUTER.post("/create_user", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_new_user(user: NewUser) -> BackendUserDict:
    """Create a new user.

    The flow and logic here is the following:
    First, check if the user already exists. If so, raise an exception.
    Then, use the provided user credentials to check if the user is valid, i.e., if the
    user is allowed to create new users.
    This check is done by the admin backend.
    Finally, create the new user.

    """
    admin_backend = get_backend(
        CONFIG.admin_backend,
        settings={
            "mongo_username": user.username,
            "mongo_password": user.password,
        },
    )

    if TYPE_CHECKING:  # pragma: no cover
        assert isinstance(admin_backend, AdminBackend)  # nosec

    if admin_backend.get_user(user.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already exists: username={user.username}",
        )

    try:
        new_user = admin_backend.create_user(user)
    except admin_backend.write_access_exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User (username={user.username}) not allowed to create new users.",
        ) from exc

    return new_user
