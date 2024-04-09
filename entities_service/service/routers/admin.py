"""The `_admin` router and endpoints.

This router is used for creating entities.

Endpoints in this router are not documented in the OpenAPI schema.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Response, status

from entities_service.models import URI_REGEX, Entity, get_uri
from entities_service.service.backend import get_backend
from entities_service.service.config import CONFIG
from entities_service.service.security import verify_token

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


LOGGER = logging.getLogger(__name__)


ROUTER = APIRouter(
    prefix="/_admin",
    tags=["Admin"],
    include_in_schema=CONFIG.debug,
    dependencies=[Depends(verify_token)],
)


# Entity-related endpoints
@ROUTER.post(
    "/create",
    response_model=list[Entity] | Entity | None,
    response_model_by_alias=True,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_entities(
    entities: list[Entity] | Entity,
    response: Response,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Create one or more SOFT entities."""
    # Parse 'entities'
    if isinstance(entities, list):
        # Check if there are any entities to create
        if not entities:
            response.status_code = status.HTTP_204_NO_CONTENT
            return None
    else:
        entities = [entities]

    write_fail_exception = HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=(
            "Could not create entit{suffix_entit} with uri{suffix_uri}: {uris}".format(
                suffix_entit="y" if len(entities) == 1 else "ies",
                suffix_uri="" if len(entities) == 1 else "s",
                uris=", ".join(get_uri(entity) for entity in entities),
            )
        ),
    )

    # Determine backends needed
    namespace_entities_mapping: dict[str | None, list[Entity]] = defaultdict(list)

    for entity in entities:
        if (match := URI_REGEX.match(get_uri(entity))) is None:
            raise write_fail_exception

        namespace_entities_mapping[match.group("specific_namespace")].append(entity)

    # Create entities
    created_entities: list[dict[str, Any]] = []
    for namespace, namespaced_entities in namespace_entities_mapping.items():
        namespaced_entities_backend = get_backend(
            CONFIG.backend, auth_level="write", db=namespace
        )

        try:
            created_namespaced_entities = namespaced_entities_backend.create(
                namespaced_entities
            )
        except namespaced_entities_backend.write_access_exception as err:
            LOGGER.error(
                "Could not create entities: uris=%s",
                ", ".join(get_uri(entity) for entity in namespaced_entities),
            )
            if created_entities:
                LOGGER.error(
                    "Already created entities: uris=%s",
                    ", ".join(
                        (
                            entity.get("uri", "")
                            or (
                                f"{entity.get('namespace', '')}"
                                f"/{entity.get('version', '')}"
                                f"/{entity.get('name', '')}"
                            )
                        )
                        for entity in created_entities
                    ),
                )
            LOGGER.exception(err)
            raise write_fail_exception from err

        if (
            created_namespaced_entities is None
            or (
                len(namespaced_entities) == 1
                and isinstance(created_namespaced_entities, list)
            )
            or (
                len(namespaced_entities) > 1
                and not isinstance(created_namespaced_entities, list)
            )
        ):
            raise write_fail_exception

        if isinstance(created_namespaced_entities, dict):
            created_entities.append(created_namespaced_entities)
        else:
            created_entities.extend(created_namespaced_entities)

    if len(created_entities) == 1:
        return created_entities[0]
    return created_entities
