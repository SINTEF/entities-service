"""Fixtures for the utils_cli tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pymongo.collection import Collection
    from typer.testing import CliRunner


@pytest.fixture(scope="session")
def cli() -> CliRunner:
    """Fixture for CLI runner."""
    from typer.testing import CliRunner

    return CliRunner(mix_stderr=False)


@pytest.fixture()
def mock_entities_collection(monkeypatch: pytest.MonkeyPatch) -> Collection:
    """Return a mock entities collection."""
    from mongomock import MongoClient

    from dlite_entities_service.service.config import CONFIG
    from dlite_entities_service.utils_cli import main

    mongo_client = MongoClient(str(CONFIG.mongo_uri))
    mock_entities_collection = mongo_client["dlite"]["entities"]

    monkeypatch.setattr(main, "ENTITIES_COLLECTION", mock_entities_collection)
    monkeypatch.setattr(
        main,
        "get_collection",
        lambda *args, **kwargs: mock_entities_collection,  # noqa: ARG005
    )

    return mock_entities_collection
