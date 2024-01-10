"""Fixtures for the utils_cli tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from typer import Typer
    from typer.testing import CliRunner


def pytest_configure(config: pytest.Config) -> None:
    """Add custom markers to pytest."""
    config.addinivalue_line("markers", "no_token: mark test to not use an auth token")


@pytest.fixture()
def cli() -> CliRunner:
    """Fixture for CLI runner."""
    import os

    from typer.testing import CliRunner

    return CliRunner(mix_stderr=False, env=os.environ.copy())


@pytest.fixture(scope="session")
def config_app() -> Typer:
    """Return the config APP."""
    from dlite_entities_service.cli._utils.global_settings import global_options
    from dlite_entities_service.cli.config import APP

    # Add global options to the APP
    # This is done by the "main" APP, and should hence be done here manually to ensure
    # they can be used
    APP.callback()(global_options)

    return APP


@pytest.fixture()
def dotenv_file(tmp_path: Path) -> Path:
    """Create a path to a dotenv file in a temporary test folder."""
    from dlite_entities_service.service.config import CONFIG

    env_file = CONFIG.model_config["env_file"]

    assert isinstance(env_file, str)

    return tmp_path / env_file


@pytest.fixture()
def _prefill_dotenv_config(dotenv_file: Path) -> None:
    """'Pre'-fill the monkeypatched dotenv config paths."""
    from dotenv import set_key

    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    env_prefix = CONFIG.model_config["env_prefix"]

    if not dotenv_file.exists():
        dotenv_file.touch()

    for field in ConfigFields:
        set_key(dotenv_file, f"{env_prefix}{field}".upper(), f"{field}_test")


@pytest.fixture()
def _use_valid_token(request: pytest.FixtureRequest) -> None:
    """Set the token to a valid one."""
    from dlite_entities_service.cli._utils.global_settings import CONTEXT
    from dlite_entities_service.models.auth import Token

    if request.node.get_closest_marker("no_token"):
        CONTEXT["token"] = None
    else:
        CONTEXT["token"] = Token(access_token="mock_token")


@pytest.fixture()
def random_valid_entity(static_dir: Path) -> dict[str, Any]:
    """Return a random valid entity."""
    import json
    from random import choice

    random_entity: Path = choice(list((static_dir / "valid_entities").glob("*.json")))
    entity: dict[str, Any] = json.loads(random_entity.read_bytes())

    assert "properties" in entity

    # SOFT5
    if isinstance(entity["properties"], list):
        entity["properties"] = [
            {key.replace("$ref", "ref"): value for key, value in property_.items()}
            for property_ in entity["properties"]
        ]

    # SOFT7
    else:
        for property_name, property_value in list(entity["properties"].items()):
            entity["properties"][property_name] = {
                key.replace("$ref", "ref"): value
                for key, value in property_value.items()
            }

    return entity


@pytest.fixture(autouse=True)
def _reset_context(pytestconfig: pytest.Config) -> None:
    """Reset the context."""
    from dlite_entities_service.cli._utils.global_settings import CONTEXT
    from dlite_entities_service.service.config import CONFIG

    CONTEXT["dotenv_path"] = (
        pytestconfig.invocation_params.dir / str(CONFIG.model_config["env_file"])
    ).resolve()
    CONTEXT["token"] = None


@pytest.fixture(autouse=True)
def _mock_config_base_url(monkeypatch: pytest.MonkeyPatch, live_backend: bool) -> None:
    """Mock the base url if using a live backend."""
    if not live_backend:
        return

    import os

    from pydantic import AnyHttpUrl

    from dlite_entities_service.service.config import CONFIG

    host, port = os.getenv("ENTITY_SERVICE_HOST", "localhost"), os.getenv(
        "ENTITY_SERVICE_PORT", "8000"
    )

    live_base_url = f"http://{host}"

    if port:
        live_base_url += f":{port}"

    monkeypatch.setattr(CONFIG, "base_url", AnyHttpUrl(live_base_url))


@pytest.fixture(params=["external", "test_client"])
def _use_test_client(
    monkeypatch: pytest.MonkeyPatch, live_backend: bool, request: pytest.FixtureRequest
) -> None:
    """Use both a test client as well as a proper external call when testing against a
    live backend."""
    if not live_backend or request.param == "external":
        return

    from fastapi.testclient import TestClient as FastAPITestClient

    from dlite_entities_service.cli.main import httpx

    class TestClient(FastAPITestClient):
        """Test client that uses the FastAPI APP."""

        def __init__(self, **kwargs) -> None:
            """Initialize the test client."""
            from dlite_entities_service.main import APP

            super().__init__(APP, **kwargs)

    monkeypatch.setattr(httpx, "Client", TestClient)


@pytest.fixture()
def non_mocked_hosts(live_backend: bool) -> list[str]:
    """Return a list of hosts that are not mocked by 'pytest-httpx."""
    import os

    if live_backend:
        host, port = os.getenv("ENTITY_SERVICE_HOST", "localhost"), os.getenv(
            "ENTITY_SERVICE_PORT", "8000"
        )

        localhost = host + (f":{port}" if port else "")
        return [localhost, host]

    return []
