"""The `_admin` router and endpoints.

This router is used for both more introspective service endpoints, such as inspecting
the current and all users, and for endpoints requiring administrative rights, such as
creating entities.

The endpoints in this router are not documented in the OpenAPI schema.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from dlite_entities_service.models import VersionedSOFTEntity, get_uri
from dlite_entities_service.models.auth import User
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.config import CONFIG
from dlite_entities_service.service.security import current_user

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from dlite_entities_service.service.backend.admin import AdminBackend


ROUTER = APIRouter(
    prefix="/_admin",
    include_in_schema=False,
    dependencies=[Depends(current_user)],
)


# Entity-related endpoints
@ROUTER.post(
    "/create",
    response_model=VersionedSOFTEntity,
    response_model_by_alias=True,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_entity(entity: VersionedSOFTEntity) -> dict[str, Any]:
    """Create a SOFT entity."""
    entities_backend = get_backend(CONFIG.backend)
    try:
        created_entity = entities_backend.create([entity])
    except entities_backend.write_access_exception as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not create entity: uri={get_uri(entity)}",
        ) from err

    if created_entity is None or isinstance(created_entity, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not create entity: uri={get_uri(entity)}",
        )
    return created_entity


@ROUTER.post(
    "/create_many",
    response_model=list[VersionedSOFTEntity],
    response_model_by_alias=True,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_entities(entities: list[VersionedSOFTEntity]) -> list[dict[str, Any]]:
    """Create many SOFT entities."""
    write_fail_exception = HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Could not create entities with uris: {}".format(
            ", ".join(get_uri(entity) for entity in entities)
        ),
    )

    # Check if there are any entities to create
    if not entities:
        return []

    # Create entities
    entities_backend = get_backend(CONFIG.backend)
    try:
        created_entities = entities_backend.create(entities)
    except entities_backend.write_access_exception as err:
        raise write_fail_exception from err

    if created_entities is None:
        raise write_fail_exception

    if not isinstance(created_entities, list):
        created_entities = [created_entities]

    return created_entities


# Admin endpoints
@ROUTER.get("/users", response_model=list[User])
async def get_users() -> list[dict[str, Any]]:
    """Get all users."""
    admin_backend = get_backend(CONFIG.admin_backend)

    if TYPE_CHECKING:  # pragma: no cover
        assert isinstance(admin_backend, AdminBackend)  # nosec

    return admin_backend.get_users()


@ROUTER.get("/users/me", response_model=User)
async def get_users_me(current_user: Annotated[User, Depends(current_user)]) -> User:
    """Get the current user."""
    return current_user
