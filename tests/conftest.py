"""Pytest configuration file."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

    from pymongo.collection import Collection


@pytest.fixture(scope="session")
def static_dir() -> Path:
    """Return the path to the static directory."""
    from pathlib import Path

    return (Path(__file__).parent / "static").resolve()


@pytest.fixture(scope="session")
def mongo_test_collection(static_dir: Path) -> Collection:
    """Add MongoDB test data, returning the MongoDB collection."""
    import yaml
    from mongomock import MongoClient

    from dlite_entities_service.config import CONFIG

    client_kwargs = {
        "username": CONFIG.mongo_user,
        "password": CONFIG.mongo_password.get_secret_value()
        if CONFIG.mongo_password is not None
        else None,
    }
    for key, value in list(client_kwargs.items()):
        if value is None:
            client_kwargs.pop(key, None)

    MOCK_ENTITIES_COLLECTION = MongoClient(
        str(CONFIG.mongo_uri), **client_kwargs
    ).dlite.entities

    MOCK_ENTITIES_COLLECTION.insert_many(yaml.safe_load((static_dir / "entities.yaml").read_text()))

    return MOCK_ENTITIES_COLLECTION


@pytest.fixture(autouse=True)
def mock_backend_entities_collection(monkeypatch: pytest.MonkeyPatch, mongo_test_collection: Collection) -> None:
    from dlite_entities_service import backend

    monkeypatch.setattr(backend, "ENTITIES_COLLECTION", mongo_test_collection)


@pytest.fixture
def get_version_name() -> Callable[[str], tuple[str, str]]:
    """Return the version and name part of a uri."""
    import re

    def _get_version_name(uri: str) -> tuple[str, str]:
        """Return the version and name part of a uri."""
        match = re.match(
            r"^http://onto-ns\.com/meta/(?P<version>[^/]+)/(?P<name>[^/]+)$", uri
        )
        assert match is not None, (
            f"Could not retrieve version and name from {uri!r}. "
            "URI must be of the form: "
            "http://onto-ns.com/meta/{version}/{name}"
        )

        return match.group("version") or "", match.group("name") or ""

    return _get_version_name


@pytest.fixture
def get_uri() -> Callable[[dict[str, Any], str], str]:
    """Return the uri for an entity."""

    def _get_uri(entity: dict[str, Any]) -> str:
        """Return the uri for an entity."""
        namespace = entity.get("namespace")
        version = entity.get("version")
        name = entity.get("name")
        if any(_ is None for _ in (namespace, version, name)):
            error_message = (
                "Could not retrieve namespace, version, and/or name from test entities."
            )
            raise RuntimeError(error_message)
        return f"{namespace}/{version}/{name}"
    
    return _get_uri
