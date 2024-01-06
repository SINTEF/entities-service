"""Admin backend for the Entities Service."""
from __future__ import annotations

import logging
from collections.abc import Generator
from typing import TYPE_CHECKING, Annotated, TypedDict

from pydantic import (
    Field,
    SecretBytes,
    SecretStr,
)
from pymongo.errors import InvalidDocument, PyMongoError

from dlite_entities_service.service.backend.backend import (
    Backend,
    BackendError,
    BackendSettings,
)
from dlite_entities_service.service.backend.mongodb import (
    MongoDBBackendWriteAccessError,
    get_client,
)
from dlite_entities_service.service.config import CONFIG, MongoDsn

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator, Sequence
    from typing import Any

    from pydantic import AnyHttpUrl

    from dlite_entities_service.models import VersionedSOFTEntity


LOGGER = logging.getLogger(__name__)


class BackendUserDict(TypedDict):
    """A new user."""

    username: str
    full_name: str | None
    roles: list[dict[str, str]]


# Exceptions
class AdminBackendError(BackendError, PyMongoError, InvalidDocument):
    """Any MongoDB backend error exception."""


AdminBackendWriteAccessError = (
    AdminBackendError,
    MongoDBBackendWriteAccessError,
)
"""Exception raised when write access is denied."""


# Data models
class AdminBackendSettings(BackendSettings):
    """Settings for the admin backend."""

    mongo_uri: Annotated[
        MongoDsn, Field(description="The MongoDB URI.")
    ] = CONFIG.mongo_uri

    mongo_username: Annotated[
        SecretStr | SecretBytes, Field(description="The MongoDB username.")
    ] = CONFIG.admin_user or SecretStr(CONFIG.mongo_user)

    mongo_password: Annotated[
        SecretStr | SecretBytes, Field(description="The MongoDB password.")
    ] = (CONFIG.admin_password or CONFIG.mongo_password)

    mongo_db: Annotated[
        str,
        Field(
            description=(
                "Name of the MongoDB database for storing admin data in the Entities "
                "Service."
            ),
        ),
    ] = CONFIG.admin_db


# Backend class
class AdminBackend(Backend):
    """Admin backend for the Entities Service."""

    _settings_model: type[AdminBackendSettings] = AdminBackendSettings
    _settings: AdminBackendSettings

    def __init__(
        self, settings: AdminBackendSettings | dict[str, Any] | None = None
    ) -> None:
        super().__init__(settings)

        username, password = (
            self._settings.mongo_username.get_secret_value(),
            self._settings.mongo_password.get_secret_value(),
        )
        if isinstance(username, bytes):
            username = username.decode()
        if isinstance(password, bytes):
            password = password.decode()

        self._db = get_client(
            uri=str(self._settings.mongo_uri),
            username=username,
            password=password,
        )[self._settings.mongo_db]

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: uri={self._settings.mongo_uri}"

    # Exceptions
    @property
    def write_access_exception(self) -> tuple:
        return AdminBackendWriteAccessError

    def get_user(self, username: str) -> BackendUserDict | None:
        """Get user with given username."""
        raw_user: list[dict[str, Any]] = self._db.command(
            "usersInfo", usersInfo=username, showCustomData=True
        )["users"]

        if not raw_user:
            return None

        if len(raw_user) > 1:
            raise AdminBackendError(f"Multiple users with username {username!r} found.")

        raw_single_user = raw_user[0]

        user: BackendUserDict = {
            "username": raw_single_user["user"],
            "full_name": raw_single_user.get("customData", {}).get("full_name", None),
            "roles": raw_single_user["roles"],
        }

        return user

    def get_users(self) -> Generator[BackendUserDict, None, None]:
        """Get all users."""
        raw_users: list[dict[str, Any]] = self._db.command(
            "usersInfo", usersInfo=1, showCustomData=True
        )["users"]

        for raw_user in raw_users:
            user: BackendUserDict = {
                "username": raw_user["user"],
                "full_name": raw_user.get("customData", {}).get("full_name", None),
                "roles": raw_user["roles"],
            }

            yield user

    def initialize_entities_backend(self) -> None:
        """Initialize the entities backend."""
        from dlite_entities_service.service.backend.mongodb import MongoDBBackend

        entities_backend = MongoDBBackend(
            settings={
                "mongo_username": self._settings.mongo_username.get_secret_value(),
                "mongo_password": self._settings.mongo_password,
            }
        )
        entities_backend.initialize()

    # Unused must-implement "Backend" methods
    def __contains__(self, item: Any) -> bool:
        raise NotImplementedError

    def __iter__(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    def initialize(self) -> None:
        """Initialize the backend."""
        raise NotImplementedError

    def create(
        self, entities: Sequence[VersionedSOFTEntity | dict[str, Any]]
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        raise NotImplementedError

    def read(self, entity_identity: AnyHttpUrl | str) -> dict[str, Any] | None:
        raise NotImplementedError

    def update(self, entity_identity: AnyHttpUrl | str, entity: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete(self, entity_identity: AnyHttpUrl | str) -> None:
        raise NotImplementedError

    def search(self, query: Any) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def count(self, query: Any = None) -> int:
        raise NotImplementedError
