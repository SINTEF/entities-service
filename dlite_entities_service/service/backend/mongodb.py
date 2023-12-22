"""Backend implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field, SecretBytes, SecretStr
from pymongo import MongoClient
from pymongo.errors import (
    BulkWriteError,
    InvalidDocument,
    PyMongoError,
    WriteConcernError,
    WriteError,
)

from dlite_entities_service.models import URI_REGEX, SOFTModelTypes
from dlite_entities_service.service.backend.backend import (
    Backend,
    BackendError,
    BackendSettings,
    BackendWriteAccessError,
)
from dlite_entities_service.service.config import CONFIG, MongoDsn

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator, Sequence
    from typing import Any, TypedDict

    from pydantic import AnyHttpUrl
    from pymongo.collection import Collection

    from dlite_entities_service.models import VersionedSOFTEntity

    class URIParts(TypedDict):
        """The parts of a SOFT entity URI."""

        namespace: str
        version: str
        name: str


MONGO_CLIENTS: dict[str, MongoClient] | None = None


class MongoDBBackendError(BackendError, PyMongoError, InvalidDocument):
    """Any MongoDB backend error exception."""


class MongoDBBackendWriteAccessError(
    MongoDBBackendError,
    BackendWriteAccessError,
    WriteConcernError,
    BulkWriteError,
    WriteError,
):
    """Exception raised when write access is denied."""


class MongoDBSettings(BackendSettings):
    """Settings for the MongoDB backend.

    Use default username and password for read access.
    """

    mongo_uri: Annotated[
        MongoDsn, Field(description="The MongoDB URI.")
    ] = CONFIG.mongo_uri

    mongo_username: Annotated[
        str, Field(description="The MongoDB username.")
    ] = CONFIG.mongo_user

    mongo_password: Annotated[
        SecretStr | SecretBytes,
        Field(
            None,
            description=(
                "The MongoDB password. If not provided, the password will be read "
                "from the environment variable MONGO_PASSWORD."
            ),
        ),
    ] = CONFIG.mongo_password

    mongo_db: Annotated[str, Field(description="The MongoDB database.")] = (
        CONFIG.mongo_db or "entities_service"
    )

    mongo_collection: Annotated[str, Field(description="The MongoDB collection.")] = (
        CONFIG.mongo_collection or "entities"
    )


def get_client(
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> MongoClient:
    """Get the MongoDB client."""
    global MONGO_CLIENTS  # noqa: PLW0603

    uri = uri or str(CONFIG.mongo_uri)
    username = username or CONFIG.mongo_user

    cache_key = f"{uri}{username}"

    if MONGO_CLIENTS is not None and cache_key in MONGO_CLIENTS:
        return MONGO_CLIENTS[cache_key]

    client_kwargs = {
        "username": username,
        "password": password
        or (
            CONFIG.mongo_password.get_secret_value()
            if CONFIG.mongo_password is not None
            else None
        ),
    }
    for key, value in list(client_kwargs.items()):
        if value is None:
            client_kwargs.pop(key, None)

    new_client = MongoClient(uri, **client_kwargs)

    if MONGO_CLIENTS is None:
        MONGO_CLIENTS = {cache_key: new_client}
    else:
        MONGO_CLIENTS[cache_key] = new_client

    return MONGO_CLIENTS[cache_key]


def get_collection(
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
    database: str | None = None,
    collection: str | None = None,
) -> Collection:
    """Get the MongoDB collection for entities."""
    mongo_client = get_client(uri, username, password)
    return mongo_client[database][collection]


class MongoDBBackend(Backend):
    """Backend implementation for MongoDB."""

    _settings_model: type[MongoDBSettings] = MongoDBSettings
    _settings: MongoDBSettings

    def __init__(
        self, settings: MongoDBSettings | dict[str, Any] | None = None
    ) -> None:
        super().__init__(settings)

        password = self._settings.mongo_password.get_secret_value()
        if isinstance(password, bytes):
            password = password.decode()

        self._collection = get_collection(
            uri=str(self._settings.mongo_uri),
            username=self._settings.mongo_username,
            password=password,
            database=self._settings.mongo_db,
            collection=self._settings.mongo_collection,
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: uri={self._settings.mongo_uri}"

    # Exceptions
    @property
    def write_access_exception(self) -> type[MongoDBBackendWriteAccessError]:
        return MongoDBBackendWriteAccessError

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._collection.find({}, projection={"_id": False}))

    def __len__(self) -> int:
        return self._collection.count_documents({})

    def create(
        self, entities: Sequence[VersionedSOFTEntity | dict[str, Any]]
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Create one or more entities in the MongoDB."""
        entities = [
            entity.model_dump(by_alias=True, mode="json", exclude_unset=True)
            if isinstance(entity, SOFTModelTypes)
            else entity
            for entity in entities
        ]

        result = self._collection.insert_many(entities)
        if len(result.inserted_ids) > 1:
            return list(
                self._collection.find(
                    {"_id": {"$in": result.inserted_ids}}, projection={"_id": False}
                )
            )

        return self._collection.find_one(
            {"_id": result.inserted_ids[0]}, projection={"_id": False}
        )

    def read(self, entity_identity: AnyHttpUrl | str) -> dict[str, Any] | None:
        """Read an entity from the MongoDB."""
        filter = self._single_uri_query(str(entity_identity))
        return self._collection.find_one(filter, projection={"_id": False})

    def update(self, entity_identity: AnyHttpUrl | str, entity: dict[str, Any]) -> None:
        """Update an entity in the MongoDB."""
        filter = self._single_uri_query(str(entity_identity))
        self._collection.update_one(filter, {"$set": entity})

    def delete(self, entity_identity: AnyHttpUrl | str) -> None:
        """Delete an entity in the MongoDB."""
        filter = self._single_uri_query(str(entity_identity))
        self._collection.delete_one(filter)

    def search(self, query: Any) -> Iterator[dict[str, Any]]:
        """Search for entities."""
        query = query or {}

        if not isinstance(query, dict):
            raise TypeError(f"Query must be a dict for {self.__class__.__name__}.")

        return self._collection.find(query)

    def count(self, query: Any = None) -> int:
        """Count entities."""
        query = query or {}

        if not isinstance(query, dict):
            raise TypeError(f"Query must be a dict for {self.__class__.__name__}.")

        return self._collection.count_documents(query)

    # MongoDBBackend specific methods
    def _single_uri_query(self, uri: str) -> dict[str, Any]:
        """Build a query for a single URI."""
        if (match := URI_REGEX.match(uri)) is not None:
            uri_parts: URIParts = match.groupdict()  # type: ignore[assignment]
        else:
            raise ValueError(f"Invalid entity URI: {uri}")

        if not all(uri_parts.values()):
            raise ValueError(f"Invalid entity URI: {uri}")

        return {"$or": [uri_parts, {"uri": uri}]}
