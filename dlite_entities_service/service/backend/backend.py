"""Generic backend class for the Entities Service."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING

from dlite_entities_service.models import SOFTModelTypes, VersionedSOFTEntity, get_uri

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator
    from typing import Any

    from pydantic import AnyHttpUrl


class Backend(ABC):
    """Interface/ABC for a backend."""

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self._settings = settings or {}

    @property
    def settings(self) -> dict[str, Any]:
        """Get the settings."""
        return self._settings

    @settings.setter
    def settings(self, settings: dict[str, Any]) -> None:
        """Set the settings."""
        self._settings = settings

    @settings.deleter
    def settings(self) -> None:
        """Delete the settings."""
        self._settings = {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(settings={self.settings!r})"

    def __str__(self) -> str:
        representation = self.__class__.__name__

        if self.settings:
            representation += ": "
            representation += ", ".join(
                f"{key}={value}" for key, value in self.settings.items()
            )

        return representation

    # Container protocol methods
    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str):
            return self.read(item) is not None

        if isinstance(item, SOFTModelTypes):
            return self.read(get_uri(item)) is not None

        return False

    @abstractmethod
    def __iter__(self) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError

    # Backend methods (CRUD)
    @abstractmethod
    def create(
        self, entities: Sequence[VersionedSOFTEntity | dict[str, Any]]
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Create an entity in the backend."""
        raise NotImplementedError

    @abstractmethod
    def read(self, entity_identity: AnyHttpUrl | str) -> dict[str, Any] | None:
        """Read an entity from the backend."""
        raise NotImplementedError

    @abstractmethod
    def update(self, entity_identity: AnyHttpUrl | str, entity: dict[str, Any]) -> None:
        """Update an entity in the backend."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_identity: AnyHttpUrl | str) -> None:
        """Delete an entity in the backend."""
        raise NotImplementedError

    # Backend methods (search)
    @abstractmethod
    def search(self, query: Any) -> Iterator[dict[str, Any]]:
        """Search for entities."""
        raise NotImplementedError

    @abstractmethod
    def count(self, query: Any = None) -> int:
        """Count entities."""
        raise NotImplementedError
