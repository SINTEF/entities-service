"""The main application module."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path as sysPath
from typing import TYPE_CHECKING, Annotated

from fastapi import FastAPI, HTTPException, Path, status

from entities_service import __version__
from entities_service.models import (
    Entity,
    EntityNameType,
    EntityVersionType,
)
from entities_service.service.backend import get_backend
from entities_service.service.config import CONFIG
from entities_service.service.logger import setup_logger
from entities_service.service.routers import get_routers

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


LOGGER = logging.getLogger("entities_service")


# Application lifespan function
@asynccontextmanager
async def lifespan(_: FastAPI):
    """Add lifespan events to the application."""
    # Initialize logger
    setup_logger()

    LOGGER.debug("Starting service with config: %s", CONFIG)

    # Initialize backend with core namespace
    get_backend(CONFIG.backend, auth_level="write")

    # Run application
    yield


# Setup application
APP = FastAPI(
    title="Entities Service",
    version=__version__,
    description=(
        sysPath(__file__).resolve().parent.parent.resolve() / "README.md"
    ).read_text(encoding="utf8"),
    lifespan=lifespan,
    root_path=CONFIG.base_url.path if CONFIG.base_url.path != "/" else "",
)

# Add routers
for router in get_routers():
    APP.include_router(router)


async def _get_entity(version: str, name: str, db: str | None = None) -> dict[str, Any]:
    """Utility function for the endpoints to retrieve an entity."""
    uri = f"{str(CONFIG.base_url).rstrip('/')}"

    if db:
        uri += f"/{db}"

    uri += f"/{version}/{name}"

    entity = get_backend(db=db).read(uri)

    if entity is None:
        raise ValueError(f"Could not find entity: uri={uri}")

    return entity


@APP.get(
    "/{version}/{name}",
    response_model=Entity,
    response_model_by_alias=True,
    response_model_exclude_unset=True,
    tags=["Entities"],
)
async def get_basic_entity(
    version: Annotated[EntityVersionType, Path(title="Entity version")],
    name: Annotated[EntityNameType, Path(title="Entity name")],
) -> dict[str, Any]:
    """Get an entity from the core namespace."""
    try:
        return await _get_entity(version=version, name=name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@APP.get(
    "/{specific_namespace:path}/{version}/{name}",
    response_model=Entity,
    response_model_by_alias=True,
    response_model_exclude_unset=True,
    tags=["Entities"],
)
async def get_namespaced_entity(
    specific_namespace: Annotated[
        str,
        Path(
            title="Specific namespace",
            description="The specific namespace part of the URI.",
        ),
    ],
    version: Annotated[EntityVersionType, Path(title="Entity version")],
    name: Annotated[EntityNameType, Path(title="Entity name")],
) -> dict[str, Any]:
    """Get an entity from a specific namespace."""
    try:
        return await _get_entity(version=version, name=name, db=specific_namespace)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
