"""Utility functions for the service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from entities_service.service.backend import get_backend
from entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


async def _add_dimensions(entity: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Utility function for the endpoints to add dimensions to an entity."""
    if isinstance(entity, list):
        for entity_ in entity:
            await _add_dimensions(entity_)
        return

    if "dimensions" not in entity:
        # SOFT5
        if isinstance(entity["properties"], list):
            entity["dimensions"] = []

        # SOFT7
        elif isinstance(entity["properties"], dict):
            entity["dimensions"] = {}

        else:
            raise ValueError(f"Invalid entity: uri={entity['uri']}")


async def _get_entity(version: str, name: str, db: str | None = None) -> dict[str, Any]:
    """Utility function for the endpoints to retrieve an entity."""
    uri = f"{str(CONFIG.base_url).rstrip('/')}"

    if db:
        uri += f"/{db}"

    uri += f"/{version}/{name}"

    entity = get_backend(CONFIG.backend, auth_level="read", db=db).read(uri)

    if entity is None:
        raise ValueError(f"Could not find entity: uri={uri}")

    await _add_dimensions(entity)

    return entity


async def _get_entities(db: str | None) -> list[dict[str, Any]]:
    """Utility function for the endpoints to retrieve all endpoints from the
    namespace/db-specific backend."""
    entities = list(get_backend(CONFIG.backend, auth_level="read", db=db))

    await _add_dimensions(entities)

    return entities
