"""Authentication module for the Entities Service."""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from dlite_entities_service.models.auth import Token
from dlite_entities_service.service.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
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
