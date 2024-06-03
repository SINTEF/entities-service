"""The `_api` router and endpoints.

This router is used for more introspective service endpoints.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import AnyHttpUrl
from pydantic.networks import AnyUrl

from entities_service.models import URI_REGEX, Entity, EntityNamespaceType
from entities_service.service.backend import get_backend, get_dbs
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
        list[AnyHttpUrl | str],
        Query(
            alias="namespace",
            description=(
                "A namespace wherein to list all entities. Can be supplied multiple "
                "times - entities will be returned as an aggregated, flat list."
            ),
        ),
    ] = []  # noqa: B006
) -> list[dict[str, Any]]:
    """List all entities in the given namespace(s)."""
    # Format namespaces
    parsed_namespaces: set[str | None] = set()
    bad_namespaces: list[AnyHttpUrl | str] = []

    for namespace in namespaces:
        if isinstance(namespace, AnyUrl):
            # Validate namespace and retrieve the specific namespace (if any)
            if (match := URI_REGEX.match(str(namespace))) is None:
                LOGGER.error("Namespace %r does not match the URI regex.", namespace)
                bad_namespaces.append(namespace)
                continue

            # Replace the namespace with the specific namespace
            # This will be `None` if the namespace is the "core" namespace
            parsed_namespaces.add(match.group("specific_namespace"))
        elif namespace.strip() == "":
            parsed_namespaces.add(None)
        else:
            # Add namespace as is
            parsed_namespaces.add(namespace)

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
        # Use the default namespace if none are given
        parsed_namespaces.add(None)

    # Retrieve entities
    entities = []
    for namespace in parsed_namespaces:
        # Retrieve entities from the database
        entities.extend(await retrieve_entities(namespace))

    return entities


@ROUTER.get(
    "/namespaces",
    response_model=list[EntityNamespaceType],
    response_model_by_alias=True,
    response_model_exclude_unset=True,
)
async def list_namespaces() -> list[str]:
    """List all namespaces for current in the given namespace(s).

    Currently, a specific namespace is equivalent to a database in the backend.
    And the "core" namespace is equivalent to the default database in the backend.

    Furthermore, when retrieving a backend object, a specific database is specified.
    If the database is left unspecified, the default database is used.
    This is equivalent to setting the requested database to `None`, which will use the
    default database, which is named by the `mongo_collection` configuration setting.

    Note, this may be confusing, as a MongoDB Collection is _not_ a database, but rather
    something more equivalent to a "table" in a relational database.

    However, currently only MongoDB is supported as a backend. In the future, other
    backends may be supported, and the configuration setting may be updated to reflect
    this. Everything else around it should remain the same.
    """
    namespaces: list[str] = []

    for db in get_dbs():
        # Retrieve the first entity from the database
        backend = get_backend(CONFIG.backend, auth_level="read", db=db)
        entity = next(backend.search())

        if "namespace" in entity:
            namespaces.append(entity["namespace"])
            continue

        if "uri" not in entity or (match := URI_REGEX.match(entity["uri"])) is None:
            LOGGER.error("Entity %r does not have a valid URI.", entity)
            raise HTTPException(
                status_code=500,
                detail=f"Entity {entity} does not have a valid URI.",
            )

        namespaces.append(match.group("namespace"))

    if not namespaces:
        raise HTTPException(
            status_code=500,
            detail="No namespaces found in the backend.",
        )

    return namespaces


async def retrieve_entities(namespace: str | None) -> list[dict[str, Any]]:
    """Retrieve entities from the namespace-specific backend."""
    backend = get_backend(CONFIG.backend, auth_level="read", db=namespace)
    return list(backend.search())
