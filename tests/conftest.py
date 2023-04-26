"""Configuration and fixtures for all pytest tests."""
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner


@pytest.fixture(scope="session")
def cli() -> "CliRunner":
    """Fixture for CLI runner."""
    from typer.testing import CliRunner

    return CliRunner(mix_stderr=False)


@pytest.fixture(scope="session")
def samples() -> "Path":
    """Fixture for samples directory."""
    from pathlib import Path

    return Path(__file__).resolve().parent / "samples"
