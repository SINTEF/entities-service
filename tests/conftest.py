"""Configuration and fixtures for all pytest tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from dlite_entities_service.service.backend.mongodb import MongoDBBackend


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the command line option to run the tests with a live backend."""
    parser.addoption(
        "--live-backend",
        action="store_true",
        default=False,
        help="Run the tests with a live backend (real MongoDB).",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest - set ENTITY_SERVICE_BACKEND env var."""
    import os

    # Set the environment variable for the MongoDB database name
    os.environ["ENTITY_SERVICE_BACKEND"] = (
        "mongodb" if config.getoption("--live-backend") else "mongomock"
    )


@pytest.fixture(scope="session")
def live_backend(request: pytest.FixtureRequest) -> bool:
    """Return whether to run the tests with a live backend."""
    import os

    required_environment_variables = (
        "ENTITY_SERVICE_MONGO_USER",
        "ENTITY_SERVICE_MONGO_PASSWORD",
    )

    value = request.config.getoption("--live-backend")

    if value:
        # Check certain environment variables are set
        assert not any(os.getenv(_) is None for _ in required_environment_variables), (
            "All required environment variables were not found to be set. "
            "Please set the following environment variables: "
            f"{', '.join(required_environment_variables)}"
        )

    # Sanity check - the ENTITY_SERVICE_BACKEND should be set to 'pymongo' if
    # the tests are run with a live backend, and 'mongomock' otherwise
    assert os.getenv("ENTITY_SERVICE_BACKEND") == ("mongodb" if value else "mongomock")

    return value


@pytest.fixture(scope="session")
def static_dir() -> Path:
    """Return the path to the static directory."""
    from pathlib import Path

    return (Path(__file__).parent / "static").resolve()


@pytest.fixture(scope="session", autouse=True)
def _mongo_test_collection(static_dir: Path, live_backend: bool) -> None:
    """Add MongoDB test data to the chosen backend."""
    import yaml

    from dlite_entities_service.service.backend import Backends, get_backend
    from dlite_entities_service.service.config import CONFIG

    # Convert all '$ref' to 'ref' in the entities.yaml file
    entities = yaml.safe_load((static_dir / "entities.yaml").read_text())
    for entity in entities:
        # SOFT5
        if isinstance(entity["properties"], list):
            for index, property_value in enumerate(list(entity["properties"])):
                entity["properties"][index] = {
                    key.replace("$", ""): value for key, value in property_value.items()
                }

        # SOFT7
        else:
            for property_name, property_value in list(entity["properties"].items()):
                entity["properties"][property_name] = {
                    key.replace("$", ""): value for key, value in property_value.items()
                }

    assert CONFIG.backend == (
        Backends.MONGODB if live_backend else Backends.MONGOMOCK
    ), (
        "The backend should be set to 'mongodb' if the tests are run with a live "
        "backend, and 'mongomock' otherwise."
    )

    # TODO: Handle authentication properly
    backend: MongoDBBackend = get_backend()

    backend._collection.insert_many(entities)


@pytest.fixture()
def client(live_backend: bool) -> TestClient:
    """Return the test client."""
    import os

    from fastapi.testclient import TestClient

    from dlite_entities_service.main import APP
    from dlite_entities_service.service.config import CONFIG

    if live_backend:
        host, port = os.getenv("ENTITY_SERVICE_HOST", "localhost"), os.getenv(
            "ENTITY_SERVICE_PORT", "8000"
        )

        return TestClient(
            app=APP,
            base_url=f"http://{host}:{port}",
        )

    return TestClient(
        app=APP,
        base_url=str(CONFIG.base_url),
    )
