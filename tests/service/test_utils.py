"""Test utils.py under service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Literal


@pytest.mark.parametrize("specific_namespace", [False, True])
async def test_get_entities(
    specific_namespace: Literal[False, True], existing_specific_namespace: str
) -> None:
    """Test _get_entities."""
    from entities_service.models import URI_REGEX
    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG
    from entities_service.service.utils import _get_entities

    db = existing_specific_namespace if specific_namespace else None

    backend = get_backend(CONFIG.backend, auth_level="read", db=db)
    entities = list(backend)

    namespace = str(CONFIG.model_fields["base_url"].default).rstrip("/")

    if specific_namespace:
        namespace += "/test"

    for entity in entities:
        if "dimensions" not in entity:
            if isinstance(entity["properties"], list):
                entity["dimensions"] = []
            elif isinstance(entity["properties"], dict):
                entity["dimensions"] = {}
            else:
                pytest.fails("Invalid entity.")

        if "namespace" in entity:
            assert entity["namespace"] == namespace

        id_key = "uri" if "uri" in entity else "identity"
        if id_key in entity:
            match = URI_REGEX.match(entity[id_key])
            assert match is not None
            assert match.group("specific_namespace") == db

    # Test with no entities
    assert await _get_entities(db) == entities
