"""The `_api` router and endpoints.

This router is used for more introspective service endpoints.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import AnyHttpUrl, ValidationError

from entities_service.models import URI_REGEX, Entity, EntityNamespaceType
from entities_service.service.backend import get_backend, get_dbs
from entities_service.service.config import CONFIG
from entities_service.service.utils import _get_entities

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
        list[str],
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

    LOGGER.debug("Namespaces: %r", namespaces)

    for namespace in namespaces:
        # Validate namespace and retrieve the specific namespace (if any)

        is_url = True
        try:
            AnyHttpUrl(namespace)
        except (ValueError, TypeError, ValidationError):
            # Not a URL
            is_url = False

        if is_url:
            # Ensure the namespace is within the base URL domain
            if not namespace.startswith(str(CONFIG.base_url).rstrip("/")):
                LOGGER.error(
                    "Namespace %r does not start with the base URL %s.",
                    namespace,
                    CONFIG.base_url,
                )
                bad_namespaces.append(namespace)
                continue

            # Extract the specific namespace from the URL

            # Handle the case of the 'namespace' being a URI (as a URL)
            if (match := URI_REGEX.match(str(namespace))) is not None:
                LOGGER.debug("Namespace %r is a URI (as a URL).", namespace)

                # Replace the namespace with the specific namespace
                # This will be `None` if the namespace is the "core" namespace
                specific_namespace = match.group("specific_namespace")

            else:
                LOGGER.debug("Namespace %r is a 'regular' full namespace.", namespace)

                specific_namespace = namespace[len(str(CONFIG.base_url).rstrip("/")) :]
                if specific_namespace.strip() in ("", "/"):
                    specific_namespace = None
                else:
                    specific_namespace = specific_namespace.lstrip("/")

            parsed_namespaces.add(specific_namespace)

        elif namespace.strip() in ("", "/"):
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

    LOGGER.debug("Parsed namespaces: %r", parsed_namespaces)

    # Retrieve entities
    entities = []
    for namespace in parsed_namespaces:
        # Retrieve entities from the database
        entities.extend(await _get_entities(namespace))

    return entities


@ROUTER.get(
    "/namespaces",
    response_model=list[EntityNamespaceType],
    response_model_by_alias=True,
    response_model_exclude_unset=True,
)
async def list_namespaces() -> list[str]:
    """List all entities' namespaces.

    This endpoint will return a list of all namespaces from existing entities in the
    backend.

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

    An entity is retrieved from each database, since the specific namespace may differ
    from the database name. Note, this is always true for the "core" namespace, which
    is equivalent to the default database.

    If no namespaces are found in the backend, a 500 error will be raised.
    """
    namespaces: list[str] = []

    for db in get_dbs():
        backend = get_backend(CONFIG.backend, auth_level="read", db=db)

        # Ignore empty backends
        if not len(backend):
            continue

        # Retrieve the first entity from the database
        entity = next(iter(backend))

        if "namespace" in entity:
            namespaces.append(entity["namespace"])
            LOGGER.debug(
                "Found namespace %r in the backend (through 'namespace').",
                entity["namespace"],
            )
            continue

        if (
            "uri" not in entity or (match := URI_REGEX.match(entity["uri"])) is None
        ):  # pragma: no cover
            # This should never actually be reached, as all entities stored in the
            # backend via the service, will have either a valid namespace or valid URI.
            LOGGER.error("Entity %r does not have a valid URI.", entity)
            raise HTTPException(
                status_code=500,
                detail=f"Entity {entity} does not have a valid URI.",
            )

        LOGGER.debug(
            "Found namespace %r in the backend (through 'uri').",
            match.group("namespace"),
        )
        namespaces.append(match.group("namespace"))

    if not namespaces:
        raise HTTPException(
            status_code=500,
            detail="No namespaces found in the backend.",
        )

    return namespaces
