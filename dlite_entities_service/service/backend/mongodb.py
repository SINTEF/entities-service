"""Backend implementation."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, SecretBytes, SecretStr
from pymongo.errors import (
    BulkWriteError,
    InvalidDocument,
    OperationFailure,
    PyMongoError,
    WriteConcernError,
    WriteError,
)

from dlite_entities_service.models import URI_REGEX, SOFTModelTypes, soft_entity
from dlite_entities_service.service.backend import Backends
from dlite_entities_service.service.backend.backend import (
    Backend,
    BackendError,
    BackendSettings,
    BackendWriteAccessError,
)
from dlite_entities_service.service.config import CONFIG, MongoDsn

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator, Sequence
    from typing import Any, TypedDict, cast

    from pydantic import AnyHttpUrl
    from pymongo import MongoClient

    from dlite_entities_service.models import VersionedSOFTEntity

    class URIParts(TypedDict):
        """The parts of a SOFT entity URI."""

        namespace: str
        version: str
        name: str


LOGGER = logging.getLogger(__name__)


MONGO_CLIENTS: dict[tuple[int, int], MongoClient] | None = None
"""Global cache for MongoDB clients.

The key is a tuple of a hash of the username and a combination of username and password
hashes.
The first hash is there to allow for quick lookup of the client for a given user when
clearing the cache for a specific user.
"""


BACKEND_DRIVER_MAPPING: dict[Backends, Literal["pymongo", "mongomock"]] = {
    Backends.MONGODB: "pymongo",
    Backends.MONGOMOCK: "mongomock",
}


# Exceptions
class MongoDBBackendError(BackendError, PyMongoError, InvalidDocument):
    """Any MongoDB backend error exception."""


MongoDBBackendWriteAccessError = (
    MongoDBBackendError,
    BackendWriteAccessError,
    WriteConcernError,
    BulkWriteError,
    WriteError,
    OperationFailure,
)
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

    mongo_driver: Annotated[
        Literal["pymongo", "mongomock"],
        Field(
            description="The MongoDB driver to use. Either 'pymongo' or 'mongomock'.",
        ),
    ] = BACKEND_DRIVER_MAPPING.get(CONFIG.backend, "pymongo")


def get_client(
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
    driver: str | None = None,
    authenticated_user: bool = False,
) -> MongoClient:
    """Get the MongoDB client."""
    if driver is None:
        driver = "pymongo"

    if driver == "pymongo":
        from pymongo import MongoClient
    elif driver == "mongomock":
        from mongomock import MongoClient
    else:
        raise ValueError(
            f"Invalid MongoDB driver: {driver}. "
            "Should be either 'pymongo' or 'mongomock'."
        )

    global MONGO_CLIENTS  # noqa: PLW0603

    username = username or CONFIG.mongo_user

    # Dealing with an authenticated user.
    if authenticated_user:
        # This means the client should have already been created.
        # We essentially by-pass having to provide a password !!! DANGEROUS !!!
        error_msg = (
            f"0 or 2 or more clients available for (authenticated) user {username!r}."
        )

        if MONGO_CLIENTS is None:
            raise MongoDBBackendError(error_msg)

        hashed_username = hash(username)

        found_clients = []
        for cache_key in MONGO_CLIENTS:
            if cache_key[0] == hashed_username:
                found_clients.append(MONGO_CLIENTS[cache_key])

        if len(found_clients) == 1:
            return found_clients[0]

        LOGGER.debug("Found %s clients for %r.", len(found_clients), username)
        LOGGER.debug("Clients: %s", found_clients)
        LOGGER.debug("Cache: %r", MONGO_CLIENTS)
        raise MongoDBBackendError(error_msg)

    # Dealing with a non-authenticated user.
    password = password or (
        CONFIG.mongo_password.get_secret_value()
        if CONFIG.mongo_password is not None
        else None
    )

    if password is None:
        raise ValueError(f"No password is given for {username!r}.")

    if TYPE_CHECKING:  # pragma: no cover
        username = cast(str, username)
        password = cast(str, password)

    cache_key = (hash(username), hash(f"{username}{password}"))

    if MONGO_CLIENTS is not None and cache_key in MONGO_CLIENTS:
        LOGGER.debug("Using cached MongoDB client for %r.", username)
        return MONGO_CLIENTS[cache_key]
    LOGGER.debug("Creating new MongoDB client for %r.", username)

    new_client = MongoClient(
        uri or str(CONFIG.mongo_uri), username=username, password=password
    )

    if MONGO_CLIENTS is None:
        MONGO_CLIENTS = {cache_key: new_client}
    else:
        MONGO_CLIENTS[cache_key] = new_client

    return MONGO_CLIENTS[cache_key]


def discard_clients_for_user(username: str) -> None:
    """Discard MongoDB clients for a user."""
    global MONGO_CLIENTS  # noqa: PLW0603

    hashed_username = hash(username)

    if MONGO_CLIENTS is None:
        return

    for cache_key in list(MONGO_CLIENTS):
        if cache_key[0] == hashed_username:
            # If this is the only client for the user, close it and then delete it,
            # resetting the global cache to None.
            if len(MONGO_CLIENTS) == 1:
                MONGO_CLIENTS[cache_key].close()
                del MONGO_CLIENTS[cache_key]
                MONGO_CLIENTS = None
                return

            # Otherwise, just delete the client from the cache.
            # Don't close it as it, as this will be detrimental for the other clients.
            del MONGO_CLIENTS[cache_key]


class MongoDBBackend(Backend):
    """Backend implementation for MongoDB."""

    _settings_model: type[MongoDBSettings] = MongoDBSettings
    _settings: MongoDBSettings

    def __init__(
        self,
        settings: MongoDBSettings | dict[str, Any] | None = None,
        authenticated_user: bool = False,
    ) -> None:
        super().__init__(settings, authenticated_user)

        password = self._settings.mongo_password.get_secret_value()
        if isinstance(password, bytes):
            password = password.decode()

        try:
            self._collection = get_client(
                uri=str(self._settings.mongo_uri),
                username=self._settings.mongo_username,
                password=password,
                driver=self._settings.mongo_driver,
                authenticated_user=authenticated_user,
            )[self._settings.mongo_db][self._settings.mongo_collection]
        except ValueError as exc:
            raise MongoDBBackendError(str(exc)) from exc

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: uri={self._settings.mongo_uri}"

    # Exceptions
    @property
    def write_access_exception(self) -> tuple:
        return MongoDBBackendWriteAccessError

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._collection.find({}, projection={"_id": False}))

    def __len__(self) -> int:
        return self._collection.count_documents({})

    def initialize(self) -> None:
        """Initialize the MongoDB backend."""
        # Check index exists
        if "URI" in (indices := self._collection.index_information()):
            if not indices["URI"].get("unique", False):
                LOGGER.warning(
                    "The URI index in the MongoDB collection is not unique. "
                    "This may cause problems when creating entities."
                )
            if indices["URI"].get("key", False) != [
                ("uri", 1),
                ("namespace", 1),
                ("version", 1),
                ("name", 1),
            ]:
                LOGGER.warning(
                    "The URI index in the MongoDB collection is not as expected. "
                    "This may cause problems when creating entities."
                )
            return

        # Create a unique index for the URI
        self._collection.create_index(
            ["uri", "namespace", "version", "name"], unique=True, name="URI"
        )

    def create(
        self, entities: Sequence[VersionedSOFTEntity | dict[str, Any]]
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Create one or more entities in the MongoDB."""
        LOGGER.info("Creating entities: %s", entities)
        LOGGER.info("The creator's user name: %s", self._settings.mongo_username)

        entities = [self._prepare_entity(entity) for entity in entities]

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

    def update(
        self,
        entity_identity: AnyHttpUrl | str,
        entity: VersionedSOFTEntity | dict[str, Any],
    ) -> None:
        """Update an entity in the MongoDB."""
        entity = self._prepare_entity(entity)
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

        return self._collection.find(query, projection={"_id": False})

    def count(self, query: Any = None) -> int:
        """Count entities."""
        query = query or {}

        if not isinstance(query, dict):
            raise TypeError(f"Query must be a dict for {self.__class__.__name__}.")

        return self._collection.count_documents(query)

    def close(self) -> None:
        """Close the MongoDB connection if using production backend."""
        if self._settings.mongo_driver == "mongomock":
            return

        super().close()
        discard_clients_for_user(self._settings.mongo_username)

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

    def _prepare_entity(
        self, entity: VersionedSOFTEntity | dict[str, Any]
    ) -> dict[str, Any]:
        """Clean and prepare the entity for interactions with the MongoDB backend."""
        if isinstance(entity, dict):
            uri = entity.get("uri", None) or (
                f"{entity.get('namespace', '')}/{entity.get('version', '')}"
                f"/{entity.get('name', '')}"
            )
            entity = soft_entity(
                error_msg=f"Invalid entity given for {uri}.",
                **entity,
            )

        if not isinstance(entity, SOFTModelTypes):
            raise TypeError(
                "Entity must be a dict or a SOFTModelTypes for "
                f"{self.__class__.__name__}."
            )

        entity = entity.model_dump(by_alias=True, mode="json", exclude_unset=True)

        # Convert all '$ref' to 'ref' in the entity
        if isinstance(entity["properties"], list):  # SOFT5
            for index, property_value in enumerate(list(entity["properties"])):
                entity["properties"][index] = {
                    key.replace("$", ""): value for key, value in property_value.items()
                }

        elif isinstance(entity["properties"], dict):  # SOFT7
            for property_name, property_value in list(entity["properties"].items()):
                entity["properties"][property_name] = {
                    key.replace("$", ""): value for key, value in property_value.items()
                }

        else:
            raise TypeError(
                f"Invalid entity properties type: {type(entity['properties'])}"
            )

        return entity
