"""The `_admin` router and endpoints.

This router is used for both more introspective service endpoints, such as inspecting
the current and all users, and for endpoints requiring administrative rights, such as
creating entities.

The endpoints in this router are not documented in the OpenAPI schema.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from dlite_entities_service.models import VersionedSOFTEntity, get_uri
from dlite_entities_service.models.auth import User, UserInBackend
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.config import CONFIG
from dlite_entities_service.service.security import current_user

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from dlite_entities_service.service.backend.admin import (
        AdminBackend,
        BackendUserDict,
    )


LOGGER = logging.getLogger(__name__)


ROUTER = APIRouter(
    prefix="/_admin",
    include_in_schema=CONFIG.debug,
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
async def create_entity(
    entity: VersionedSOFTEntity,
    current_user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    """Create a SOFT entity."""
    entities_backend = get_backend(
        CONFIG.backend,
        settings={
            "mongo_username": current_user.username,
        },
    )
    try:
        created_entity = entities_backend.create([entity])
    except entities_backend.write_access_exception as err:
        LOGGER.error("Could not create entity: uri=%s", get_uri(entity))
        LOGGER.exception(err)
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
        LOGGER.error(
            "Could not create entities: uris=%s",
            ", ".join(get_uri(entity) for entity in entities),
        )
        LOGGER.exception(err)
        raise write_fail_exception from err

    if created_entities is None:
        raise write_fail_exception

    if not isinstance(created_entities, list):
        created_entities = [created_entities]

    return created_entities


# Admin endpoints
@ROUTER.get("/users", response_model=list[User])
async def get_users() -> list[BackendUserDict]:
    """Get all users."""
    admin_backend = get_backend(CONFIG.admin_backend)

    if TYPE_CHECKING:  # pragma: no cover
        assert isinstance(admin_backend, AdminBackend)  # nosec

    return list(admin_backend.get_users())


@ROUTER.get("/users/me", response_model=UserInBackend)
async def get_users_me(
    current_user: Annotated[UserInBackend, Depends(current_user)]
) -> UserInBackend:
    """Get the current user."""
    return current_user
