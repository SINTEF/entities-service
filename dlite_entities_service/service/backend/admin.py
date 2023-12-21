"""Admin backend for the Entities Service."""
from __future__ import annotations

from typing import TYPE_CHECKING

from dlite_entities_service.service.backend.mongodb import get_client
from dlite_entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from pymongo.collection import Collection


class AdminBackend:
    """Admin backend for the Entities Service."""

    def __init__(self) -> None:
        self._db = get_client(
            uri=str(CONFIG.mongo_uri),
            username=CONFIG.admin_user.get_secret_value(),
            password=CONFIG.admin_password.get_secret_value(),
        )

    def __repr__(self) -> str:
        return f"<{self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: uri={CONFIG.mongo_uri}"

    @property
    def _users_collection(self) -> Collection:
        """Get the MongoDB collection for users."""
        return self._db[CONFIG.users_collection]

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Get user with given username."""
        return self._users_collection.find_one({"username": username})
