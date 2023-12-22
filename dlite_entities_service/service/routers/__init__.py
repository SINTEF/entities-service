"""Various routers for the service."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter


def get_routers() -> list[APIRouter]:
    """Get the routers."""
    from .admin import ROUTER as ADMIN_ROUTER
    from .auth import ROUTER as AUTH_ROUTER

    return [ADMIN_ROUTER, AUTH_ROUTER]
