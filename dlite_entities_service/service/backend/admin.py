"""Admin backend for the Entities Service."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, SecretBytes, SecretStr

from dlite_entities_service.service.backend.backend import Backend, BackendSettings
from dlite_entities_service.service.backend.mongodb import (
    MongoDBBackendWriteAccessError,
    get_client,
)
from dlite_entities_service.service.config import CONFIG, MongoDsn

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator, Sequence
    from typing import Any

    from pydantic import AnyHttpUrl
    from pymongo.collection import Collection

    from dlite_entities_service.models import VersionedSOFTEntity


class AdminBackendMongoCollections(BaseModel):
    """Names of the MongoDB collections for storing admin data."""

    users: Annotated[
        str,
        Field(
            description="Name of the MongoDB collection for storing users.",
        ),
    ] = CONFIG.users_collection


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

    mongo_collections: Annotated[
        AdminBackendMongoCollections,
        Field(
            description="Names of the MongoDB collections for storing admin data.",
        ),
    ] = AdminBackendMongoCollections()


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
    def write_access_exception(self) -> type[MongoDBBackendWriteAccessError]:
        return MongoDBBackendWriteAccessError

    @property
    def _users_collection(self) -> Collection:
        """Get the MongoDB collection for users."""
        return self._db[self._settings.mongo_collections.users]

    def get_user(self, username: str) -> dict[str, Any] | None:
        """Get user with given username."""
        return self._users_collection.find_one(
            {"username": username}, projection={"_id": False}
        )

    def get_users(self) -> list[dict[str, Any]]:
        """Get all users."""
        return list(self._users_collection.find(projection={"_id": False}))

    # Unused must-implement methods
    def __contains__(self, item: Any) -> bool:
        raise NotImplementedError

    def __iter__(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def __len__(self) -> int:
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
