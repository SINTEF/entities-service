"""The `_admin` router and endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, status

from dlite_entities_service.models import VersionedSOFTEntity, get_uri
from dlite_entities_service.service.backend import get_backend
from dlite_entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


ROUTER = APIRouter(
    prefix="/_admin",
    include_in_schema=False,
)


@ROUTER.post(
    "/create",
    response_model=VersionedSOFTEntity,
    response_model_by_alias=True,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_entity(entity: VersionedSOFTEntity) -> dict[str, Any]:
    """Create a SOFT entity."""
    backend = get_backend(CONFIG.backend)
    try:
        created_entity = backend.create([entity])
    except backend.write_access_exception as err:
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
    created_entities = get_backend(CONFIG.backend).create(entities)
    if created_entities is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create entities with uris: {}".format(
                ", ".join(get_uri(entity) for entity in entities)
            ),
        )

    if not isinstance(created_entities, list):
        created_entities = [created_entities]

    return created_entities
