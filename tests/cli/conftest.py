"""Fixtures for the utils_cli tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pymongo.collection import Collection
    from typer import Typer
    from typer.testing import CliRunner


@pytest.fixture()
def cli() -> CliRunner:
    """Fixture for CLI runner."""
    import os

    from typer.testing import CliRunner

    return CliRunner(mix_stderr=False, env=os.environ.copy())


@pytest.fixture()
def mock_entities_collection(monkeypatch: pytest.MonkeyPatch) -> Collection:
    """Return a mock entities collection."""
    from mongomock import MongoClient

    from dlite_entities_service.cli import main
    from dlite_entities_service.service.config import CONFIG

    mongo_client = MongoClient(str(CONFIG.mongo_uri))
    mock_entities_collection = mongo_client["dlite"]["entities"]

    monkeypatch.setattr(main, "ENTITIES_COLLECTION", mock_entities_collection)
    monkeypatch.setattr(
        main,
        "get_collection",
        lambda *args, **kwargs: mock_entities_collection,  # noqa: ARG005
    )

    return mock_entities_collection


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
def patch_dotenv_config_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture for monkeypatching dotenv config paths."""
    from dlite_entities_service.cli import config
    from dlite_entities_service.service.config import CONFIG

    env_file = CONFIG.model_config["env_file"]

    monkeypatch.setattr(config, "CLI_DOTENV_FILE", tmp_path / f"{env_file}_cli")
    monkeypatch.setattr(config, "SERVICE_DOTENV_FILE", tmp_path / f"{env_file}_service")

    return tmp_path


@pytest.fixture()
def _prefill_dotenv_config(patch_dotenv_config_paths: Path) -> None:
    """'Pre'-fill the monkeypatched dotenv config paths."""
    from dotenv import set_key

    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    env_file = CONFIG.model_config["env_file"]
    env_prefix = CONFIG.model_config["env_prefix"]

    for dotenv_file in ("service", "cli"):
        if not (patch_dotenv_config_paths / f"{env_file}_{dotenv_file}").exists():
            (patch_dotenv_config_paths / f"{env_file}_{dotenv_file}").touch()

        for field in ConfigFields:
            set_key(
                patch_dotenv_config_paths / f"{env_file}_{dotenv_file}",
                f"{env_prefix}{field}".upper(),
                f"{field}_{dotenv_file}_test",
            )
