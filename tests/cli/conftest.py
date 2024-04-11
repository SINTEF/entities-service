"""Fixtures for all CLI tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner


@pytest.fixture()
def cli() -> CliRunner:
    """Fixture for CLI runner."""
    import os

    from typer.testing import CliRunner

    return CliRunner(mix_stderr=False, env=os.environ.copy())


@pytest.fixture()
def tmp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / ".cache" / "entities-service"

    monkeypatch.setattr(
        "entities_service.cli._utils.generics.CACHE_DIRECTORY", cache_dir
    )
    monkeypatch.setattr(
        "entities_service.cli._utils.global_settings.CACHE_DIRECTORY", cache_dir
    )

    return cache_dir


@pytest.fixture()
def tmp_cache_file(tmp_cache_dir: Path) -> Path:
    """Create a temporary cache file."""
    return tmp_cache_dir / "oauth2_token_cache.json"


@pytest.fixture(autouse=True)
def _function_specific_cli_cache_dir(
    tmp_cache_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set the CLI cache directory to a temporary one."""
    from httpx_auth import JsonTokenFileCache

    cache = JsonTokenFileCache(str(tmp_cache_file))

    monkeypatch.setattr(
        "entities_service.cli._utils.generics.OAuth2.token_cache", cache
    )


@pytest.fixture(autouse=True)
def _reset_context(pytestconfig: pytest.Config) -> None:
    """Reset the context."""
    from entities_service.cli._utils.global_settings import CONTEXT
    from entities_service.service.config import CONFIG

    CONTEXT["dotenv_path"] = (
        pytestconfig.invocation_params.dir / str(CONFIG.model_config["env_file"])
    ).resolve()


@pytest.fixture(autouse=True)
def _large_width_consoles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the consoles' width to a large number."""
    from rich.console import Console

    monkeypatch.setattr(
        "entities_service.cli._utils.generics.OUTPUT_CONSOLE", Console(width=999)
    )
    monkeypatch.setattr(
        "entities_service.cli._utils.generics.ERROR_CONSOLE",
        Console(stderr=True, width=999),
    )
