"""The `_api` router and endpoints.

This router is used for more introspective service endpoints.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import AnyHttpUrl

from entities_service.models import URI_REGEX, Entity
from entities_service.service.backend import get_backend
from entities_service.service.config import CONFIG

LOGGER = logging.getLogger(__name__)

ROUTER = APIRouter(prefix="/_api", tags=["API"])


@ROUTER.get(
    "/entities",
    response_model=list[Entity],
    response_model_by_alias=True,
    response_model_exclude_unset=True,
)
async def list_entities(
    namespaces: Annotated[
        list[AnyHttpUrl | str] | None,
        Query(
            alias="namespace",
            description=(
                "A namespace wherein to list all entities. Can be supplied multiple "
                "times - entities will be returned as an aggregated, flat list."
            ),
        ),
    ] = None
) -> list[dict[str, Any]]:
    """List all entities in the given namespace(s)."""
    # Format namespaces
    parsed_namespaces: set[str | None] = set()
    bad_namespaces: list[AnyHttpUrl | str] = []

    for namespace in namespaces or []:
        if isinstance(namespace, AnyHttpUrl):
            # Validate namespace and retrieve the specific namespace (if any)
            if (match := URI_REGEX.match(str(namespace))) is None:
                LOGGER.error("Namespace %r does not match the URI regex.", namespace)
                bad_namespaces.append(namespace)
                continue

            # Replace the namespace with the specific namespace
            # This will be `None` if the namespace is the "core" namespace
            parsed_namespaces.add(match.group("specific_namespace"))

    if bad_namespaces:
        # Raise an error if there are any bad namespaces
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid namespace{'s' if len(bad_namespaces) > 1 else ''}: "
                f"{', '.join(map(str, bad_namespaces))}."
            ),
        )

    if not parsed_namespaces:
        return []

    # Retrieve entities
    entities = []
    for namespace in parsed_namespaces:
        # Retrieve entities from the database
        entities.extend(await retrieve_entities(namespace))

    return entities


async def retrieve_entities(namespace: str | None) -> list[dict[str, Any]]:
    """Retrieve entities from the namespace-specific backend."""
    backend = get_backend(CONFIG.backend, auth_level="read", db=namespace)
    return list(backend.search())
