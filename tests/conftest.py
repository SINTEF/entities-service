"""Configuration and fixtures for all pytest tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal, Protocol, TypedDict

    from fastapi.testclient import TestClient
    from httpx import Client

    from dlite_entities_service.service.backend.admin import AdminBackend
    from dlite_entities_service.service.backend.mongodb import MongoDBBackend

    class UserFullInfoRoleDict(TypedDict):
        """Type for the user info dictionary with roles."""

        role: str
        db: str

    class UserFullInfoDict(TypedDict):
        """Type for the full user info dictionary."""

        username: str
        password: str
        full_name: str | None
        roles: list[UserFullInfoRoleDict]

    class ClientFixture(Protocol):
        """Protocol for the client fixture."""

        def __call__(
            self, auth_role: Literal["read", "readWrite"] | None = None
        ) -> TestClient | Client:
            ...

    class GetBackendUserFixture(Protocol):
        """Protocol for the get_backend_user fixture."""

        def __call__(
            self, auth_role: Literal["read", "readWrite"] | None = None
        ) -> UserFullInfoDict:
            ...


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
    live_backend: bool = config.getoption("--live-backend")
    os.environ["ENTITY_SERVICE_BACKEND"] = "mongodb" if live_backend else "mongomock"

    # Add extra markers
    config.addinivalue_line(
        "markers",
        "skip_if_live_backend: mark test to skip it if using a live backend, "
        "optionally specify a reason why it is skipped",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Called after collection has been performed. May filter or re-order the items
    in-place."""
    if config.getoption("--live-backend"):
        # If the tests are run with a live backend, skip the tests marked with
        # 'skip_if_live_backend'
        prefix_reason = "Live backend used: {reason}"
        default_reason = "Test is skipped when using a live backend"
        for item in items:
            if "skip_if_live_backend" in item.keywords:
                marker: pytest.Mark = item.keywords["skip_if_live_backend"]

                if marker.args:
                    assert len(marker.args) == 1, (
                        "The 'skip_if_live_backend' marker can only have one "
                        "argument."
                    )

                    reason = marker.args[0]
                elif marker.kwargs and "reason" in marker.kwargs:
                    reason = marker.kwargs["reason"]
                else:
                    reason = default_reason

                assert isinstance(
                    reason, str
                ), "The reason for skipping the test must be a string."

                # The marker does not have a reason
                item.add_marker(
                    pytest.mark.skip(reason=prefix_reason.format(reason=reason))
                )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Called after the Session object has been created and before performing
    collection and entering the run test loop.

    Used together with `pytest_sessionfinish()` to temporarily rename a local `.env`
    file.
    """
    import shutil
    from pathlib import Path

    if session.config.getoption("--live-backend"):
        # If the tests are run with a live backend, there is no need to rename the
        # local '.env' file
        return

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

    if session.config.getoption("--live-backend"):
        # If the tests are run with a live backend, there is no need to return the
        # local '.env' file
        return

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
    import warnings

    required_environment_variables = (
        "ENTITY_SERVICE_HOST",
        "ENTITY_SERVICE_PORT",
    )

    value = request.config.getoption("--live-backend")

    # Check certain environment variables are set
    if value and any(os.getenv(_) is None for _ in required_environment_variables):
        with warnings.catch_warnings():
            warnings.simplefilter("default")
            warnings.warn(
                "All required environment variables were not found to be set. "
                "Please set the following environment variables: "
                f"{', '.join(required_environment_variables)}",
                stacklevel=1,
            )

    # Sanity check - the ENTITY_SERVICE_BACKEND should be set to 'pymongo' if
    # the tests are run with a live backend, and 'mongomock' otherwise
    assert os.getenv("ENTITY_SERVICE_BACKEND") == "mongodb" if value else "mongomock"

    return value


@pytest.fixture(scope="session")
def static_dir() -> Path:
    """Return the path to the static directory."""
    from pathlib import Path

    return (Path(__file__).parent / "static").resolve()


@pytest.fixture(scope="session")
def get_backend_user() -> GetBackendUserFixture:
    """Return a function to get the backend user."""
    from dlite_entities_service.service.config import CONFIG

    def _get_backend_user(
        auth_role: Literal["read", "readWrite"] | None = None
    ) -> UserFullInfoDict:
        """Return the backend user for the given authentication role."""
        if auth_role is None:
            auth_role = "read"

        assert auth_role in (
            "read",
            "readWrite",
        ), "The authentication role must be either 'read' or 'readWrite'."

        if auth_role == "read":
            password = CONFIG.mongo_password.get_secret_value()
            full_info_dict: UserFullInfoDict = {
                "username": CONFIG.mongo_user,
                "password": password.decode()
                if isinstance(password, bytes)
                else password,
                "full_name": CONFIG.mongo_user,
                "roles": [
                    {
                        "role": "read",
                        "db": CONFIG.mongo_db,
                    }
                ],
            }
            return full_info_dict

        full_info_dict: UserFullInfoDict = {
            "username": "test_write_user",
            "password": "writer",
            "full_name": "Test write user",
            "roles": [
                {
                    "role": "readWrite",
                    "db": CONFIG.mongo_db,
                }
            ],
        }
        return full_info_dict

    return _get_backend_user


@pytest.fixture(scope="session", autouse=True)
def _mongo_test_collection(
    static_dir: Path, live_backend: bool, get_backend_user: GetBackendUserFixture
) -> None:
    """Add MongoDB test data to the chosen backend."""
    import yaml

    from dlite_entities_service.service.backend import Backends, get_backend
    from dlite_entities_service.service.config import CONFIG

    # Convert all '$ref' to 'ref' in the entities.yaml file
    entities: list[dict[str, Any]] = yaml.safe_load(
        (static_dir / "entities.yaml").read_text()
    )
    for entity in entities:
        # SOFT5
        if isinstance(entity["properties"], list):
            for index, property_value in enumerate(list(entity["properties"])):
                entity["properties"][index] = {
                    key.replace("$", ""): value for key, value in property_value.items()
                }

        # SOFT7
        elif isinstance(entity["properties"], dict):
            for property_name, property_value in list(entity["properties"].items()):
                entity["properties"][property_name] = {
                    key.replace("$", ""): value for key, value in property_value.items()
                }

        else:
            raise TypeError(
                f"Invalid type for entity['properties']: {type(entity['properties'])}"
            )

    assert CONFIG.backend == (
        Backends.MONGODB if live_backend else Backends.MONGOMOCK
    ), (
        "The backend should be set to 'mongodb' if the tests are run with a live "
        "backend, and 'mongomock' otherwise."
    )

    backend_settings = {}
    if live_backend:
        # Add test users to the database
        admin_backend: AdminBackend = get_backend(
            "admin",
            settings={
                "mongo_username": CONFIG.admin_user.get_secret_value()
                if CONFIG.admin_user is not None
                else "root",
                "mongo_password": CONFIG.admin_password.get_secret_value()
                if CONFIG.admin_password is not None
                else "root",
            },
        )

        existing_users: list[str] = [
            user["user"]
            for user in admin_backend._db.command("usersInfo", usersInfo=1)["users"]
        ]

        for auth_role in ("read", "readWrite"):
            user_full_info = get_backend_user(auth_role)
            if user_full_info["username"] not in existing_users:
                admin_backend._db.command(
                    "createUser",
                    createUser=user_full_info["username"],
                    pwd=user_full_info["password"],
                    customData={"full_name": user_full_info["full_name"]},
                    roles=user_full_info["roles"],
                )

            if auth_role == "readWrite":
                # Use backend settings with write rights
                backend_settings = {
                    "mongo_username": user_full_info["username"],
                    "mongo_password": user_full_info["password"],
                }

    # Get entities backend
    backend: MongoDBBackend = get_backend(settings=backend_settings)

    if live_backend:
        # Remove the test entities from the database
        backend._collection.delete_many({})

    # Add the test entities to the database
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

        monkeypatch.setattr(
            "dlite_entities_service.service.backend.clear_caches", lambda: None
        )


@pytest.fixture()
def client(
    live_backend: bool, get_backend_user: GetBackendUserFixture
) -> ClientFixture:
    """Return the test client."""
    import os

    from fastapi.testclient import TestClient
    from httpx import Client

    from dlite_entities_service.main import APP
    from dlite_entities_service.models.auth import Token
    from dlite_entities_service.service.config import CONFIG

    def _client(
        auth_role: Literal["read", "readWrite"] | None = None
    ) -> TestClient | Client:
        """Return the test client with the given authentication role."""
        if not live_backend:
            return TestClient(
                app=APP,
                base_url=str(CONFIG.base_url),
            )

        if auth_role is None:
            auth_role = "read"

        assert auth_role in ("read", "readWrite"), (
            f"Invalid authentication role {auth_role!r}. Must be either 'read' or "
            "'readWrite'."
        )

        host, port = os.getenv("ENTITY_SERVICE_HOST", "localhost"), os.getenv(
            "ENTITY_SERVICE_PORT", "8000"
        )

        base_url = f"http://{host}"

        if port:
            base_url += f":{port}"

        backend_user = get_backend_user(auth_role)

        with Client(base_url=base_url) as temp_client:
            response = temp_client.post(
                "/_auth/token",
                data={
                    "grant_type": "password",
                    "username": backend_user["username"],
                    "password": backend_user["password"],
                },
            )

        assert response.is_success, response.text
        try:
            token = Token(**response.json())
        except Exception as exc:
            raise ValueError(
                "Could not parse the response from the token endpoint. "
                f"Response:\n{response.text}"
            ) from exc

        authentication_header = {
            "Authorization": f"{token.token_type} {token.access_token}"
        }

        return Client(
            base_url=f"http://{host}:{port}",
            headers=authentication_header,
        )

    return _client


@pytest.fixture()
def non_mocked_hosts(live_backend: bool) -> list[str]:
    """Return a list of hosts that are not mocked by 'pytest-httpx."""
    import os

    if live_backend:
        return [os.getenv("ENTITY_SERVICE_HOST", "localhost")]

    return []
