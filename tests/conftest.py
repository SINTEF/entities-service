"""Configuration and fixtures for all pytest tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from dlite_entities_service.service.backend.mongodb import MongoDBBackend

## Pytest configuration functions and hooks ##


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


def pytest_sessionstart(session: pytest.Session) -> None:
    """Called after the Session object has been created and before performing
    collection and entering the run test loop.

    Used together with `pytest_sessionfinish()` to temporarily rename a local `.env`
    file.
    """
    import shutil
    from pathlib import Path

    local_env_file = Path(session.startpath).resolve() / ".env"

    if local_env_file.exists():
        temporary_env_file = (
            Path(session.startpath).resolve() / ".env.temp_while_testing"
        )
        if temporary_env_file.exists():
            raise FileExistsError(
                "Could not temporarily rename local '.env' file to "
                f"'{temporary_env_file}'. File already exists."
            )

        shutil.move(local_env_file, temporary_env_file)

        if local_env_file.exists() or not temporary_env_file.exists():
            raise FileNotFoundError(
                "Could not move local '.env' file to a temporary naming."
            )


def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int  # noqa: ARG001
) -> None:
    """Called after whole test run finished, right before returning the exit status to
    the system.

    Used together with `pytest_sessionstart()` to temporarily return a local `.env`
    file.
    """
    import shutil
    from pathlib import Path

    local_env_file = Path(session.startpath).resolve() / ".env"

    if local_env_file.exists():
        raise FileExistsError(
            "The local '.env' file could not be returned to its original name "
            "because the file already exists."
        )

    temporary_env_file = Path(session.startpath).resolve() / ".env.temp_while_testing"
    if not temporary_env_file.exists():
        # The temporary file does not exist, so there is nothing to do
        return

    shutil.move(temporary_env_file, local_env_file)

    if not local_env_file.exists() or temporary_env_file.exists():
        raise FileNotFoundError(
            "Could not move local temporary '.env.temp_while_testing' file to the "
            "original '.env' naming."
        )


## Pytest fixtures ##


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

    print("Inserting entities")
    backend._collection.insert_many(entities)


@pytest.fixture(autouse=True)
def _mock_lifespan(live_backend: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the AdminBackend.initialize_entities_backend() method."""
    # Only mock the lifespan context manager if the tests are not run with a live
    # backend
    if not live_backend:
        monkeypatch.setattr(
            "dlite_entities_service.service.backend.admin.AdminBackend.initialize_entities_backend",
            lambda _: None,
        )
    # Always remove the usability of clear_caches()
    monkeypatch.setattr(
        "dlite_entities_service.service.backend.clear_caches", lambda: None
    )


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
