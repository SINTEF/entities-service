"""Configuration and fixtures for all pytest tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="session")
def samples() -> Path:
    """Fixture for samples directory."""
    from pathlib import Path

    return Path(__file__).resolve().parent / "samples"
