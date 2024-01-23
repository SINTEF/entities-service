"""Backend module.

Currently implemented backends:

- MongoDB

"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Enum with string values."""


if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from dlite_entities_service.service.backend.backend import Backend


class Backends(StrEnum):
    """Backends."""

    MONGODB = "mongodb"
    ADMIN = "admin"

    # Testing
    MONGOMOCK = "mongomock"

    def get_class(self) -> type[Backend]:
        """Get the backend class."""
        if self in (self.MONGODB, self.MONGOMOCK):
            from dlite_entities_service.service.backend.mongodb import MongoDBBackend

            return MongoDBBackend

        if self == self.ADMIN:
            from dlite_entities_service.service.backend.admin import AdminBackend

            return AdminBackend

        raise NotImplementedError(f"Backend {self} not implemented")


def get_backend(
    backend: Backends | str | None = None,
    settings: dict[str, Any] | None = None,
    authenticated_user: bool = True,
) -> Backend:
    """Get a backend instance."""
    from dlite_entities_service.service.config import CONFIG

    if backend is None:
        backend = CONFIG.backend

    try:
        backend = Backends(backend)
    except ValueError as exc:
        raise ValueError(
            f"Unknown backend: {backend}\nValid backends:\n"
            + "\n".join(f" - {_}" for _ in Backends.__members__.values())
        ) from exc

    backend_class = backend.get_class()

    # Expect an authenticated user for all backends except the admin backend.
    # But leave the choice to "re"-authenticate the user to the backend (if not the
    # admin backend).
    authenticated_user = authenticated_user and (backend != Backends.ADMIN)

    return backend_class(settings, authenticated_user=authenticated_user)


def clear_caches() -> None:
    """Clear all internal service caches."""
    from dlite_entities_service.service.backend import mongodb

    if mongodb.MONGO_CLIENTS is None:
        return

    for client in mongodb.MONGO_CLIENTS.values():
        client.close()

    mongodb.MONGO_CLIENTS = None
