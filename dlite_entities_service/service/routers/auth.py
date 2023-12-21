"""Authentication module for the Entities Service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from dlite_entities_service.models.auth import Token, TokenData, User, UserInBackend
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from dlite_entities_service.service.backend.admin import AdminBackend

# to get a string like this run:
# openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="_auth/token")

ROUTER = APIRouter(prefix="/_auth", include_in_schema=False)


def verify_password(
    plain_password: str | bytes, hashed_password: str | bytes | None
) -> bool:
    return PWD_CONTEXT.verify(plain_password, hashed_password)


def get_password_hash(password: str | bytes) -> str:
    return PWD_CONTEXT.hash(password)


def get_user(backend: AdminBackend, username: str) -> UserInBackend | None:
    if username in backend:
        user_dict = backend.get_user(username)
        return UserInBackend(**user_dict)
    return None


def authenticate_user(username: str, password: str) -> UserInBackend | bool:
    user = get_user(get_backend(CONFIG.backend), username)

    if not user:
        return False

    if not verify_password(password, user.hashed_password.get_secret_value()):
        return False

    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
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

    return jwt.encode(
        to_encode, CONFIG.private_ssl_key.get_secret_value(), algorithm=ALGORITHM
    )


async def get_current_user(token: Annotated[str, Depends(OAUTH2_SCHEME)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
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

    user = get_user(get_backend(CONFIG.backend), username=token_data.username)

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user."
        )

    return current_user


@ROUTER.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@ROUTER.get("/users/me", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return current_user
