"""Test the /_api/entities endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from ...conftest import ClientFixture


def test_list_entities(client: ClientFixture, static_dir: Path) -> None:
    """Test calling the endpoint straight up."""
    from copy import deepcopy

    import yaml

    # Load entities
    entities: list[dict[str, Any]] = yaml.safe_load(
        (static_dir / "valid_entities.yaml").read_text()
    )

    # Update entities according to the expected response
    expected_response_entities: list[dict[str, Any]] = []
    for entity in entities:
        new_response_entity = deepcopy(entity)

        if "identity" in entity:
            new_response_entity["uri"] = new_response_entity.pop("identity")

        # SOFT5 style
        if isinstance(entity["properties"], list):
            if "dimensions" not in entity:
                new_response_entity["dimensions"] = []

        # SOFT7
        elif isinstance(entity["properties"], dict):
            if "dimensions" not in entity:
                new_response_entity["dimensions"] = {}

        else:
            pytest.fail(f"Invalid entity: {entity}")

        expected_response_entities.append(new_response_entity)

    # List entities
    with client() as client_:
        response = client_.get("/_api/entities")

    response_json = response.json()

    # Check response
    assert response.status_code == 200, response_json
    assert isinstance(response_json, list), response_json
    assert len(response_json) == len(entities), response_json
    assert response_json == expected_response_entities, response_json
