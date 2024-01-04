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
    backend: Backends | str | None = None, settings: dict[str, Any] | None = None
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

    return backend_class(settings)
