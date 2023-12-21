"""Backend implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pymongo import MongoClient

from dlite_entities_service.models import URI_REGEX, SOFTModelTypes
from dlite_entities_service.service.backend.backend import Backend
from dlite_entities_service.service.config import CONFIG

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


def get_collection(
    uri: str | None = None, username: str | None = None, password: str | None = None
) -> Collection:
    """Get the MongoDB collection for entities."""
    client_kwargs = {
        "username": username or CONFIG.mongo_user,
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

    mongo_client = MongoClient(
        uri or str(CONFIG.mongo_uri),
        **client_kwargs,
    )
    return mongo_client.dlite.entities


class MongoDBBackend(Backend):
    """Backend implementation for MongoDB."""

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        super().__init__(settings)
        self._collection = get_collection(**self.settings)

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
