"""Pytest configuration file."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient
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

    MOCK_ENTITIES_COLLECTION.insert_many(
        yaml.safe_load((static_dir / "entities.yaml").read_text())
    )

    return MOCK_ENTITIES_COLLECTION


@pytest.fixture(autouse=True)
def _mock_backend_entities_collection(
    monkeypatch: pytest.MonkeyPatch, mongo_test_collection: Collection
) -> None:
    from dlite_entities_service import backend

    monkeypatch.setattr(backend, "ENTITIES_COLLECTION", mongo_test_collection)


@pytest.fixture()
def client() -> TestClient:
    """Return the test client."""
    from fastapi.testclient import TestClient

    from dlite_entities_service.config import CONFIG
    from dlite_entities_service.main import APP

    return TestClient(
        app=APP,
        base_url=str(CONFIG.base_url),
    )
