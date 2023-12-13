"""Test special error message for Python 3.12+."""
from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12), reason="Special test for Python 3.12."
)


def test_not_implemented_error() -> None:
    """Test that NotImplementedError is raised."""
    with pytest.raises(
        NotImplementedError,
        match=(
            "Python 3.12 and newer is not yet supported. Please use Python 3.10 or "
            "3.11."
        ),
    ):
        from dlite_entities_service.cli.main import APP  # noqa: F401
