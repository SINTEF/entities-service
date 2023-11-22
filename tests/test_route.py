"""Test the service's only route to retrieve DLite/SOFT entities."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

    from fastapi.testclient import TestClient


def test_get_entity(
    static_dir: Path,
    get_version_name: Callable[[str], tuple[str, str]],
    get_uri: Callable[[dict[str, Any]], str],
    client: TestClient,
) -> None:
    """Test the route to retrieve a DLite/SOFT entity."""
    import sys

    import yaml
    from fastapi import status

    entities: list[dict[str, Any]] = yaml.safe_load(
        (static_dir / "entities.yaml").read_text()
    )

    for entity in entities:
        uri = entity.get("uri") or get_uri(entity)

        version, name = get_version_name(uri)

        response = client.get(f"/{version}/{name}", timeout=5)

        assert (
            response.is_success
        ), f"Response: {response.json()}. Request: {response.request}"
        assert response.status_code == status.HTTP_200_OK, response.json()
        assert (resolved_entity := response.json()) == entity, resolved_entity

        # Validate that we can instantiate an Instance from the response
        # DLite does not support Python 3.12 yet.
        if sys.version_info < (3, 12):
            from dlite import Instance

            Instance.from_dict(resolved_entity)


def test_get_entity_not_found(client: TestClient) -> None:
    """Test that the route returns a Not Found (404) for non existant URIs."""
    from fastapi import status

    version, name = "0.0", "NonExistantEntity"
    response = client.get(f"/{version}/{name}", timeout=5)

    assert not response.is_success, "Non existant (valid) URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Response:\n\n{response.json()}"


def test_get_entity_invalid_uri(client: TestClient) -> None:
    """Test that the service raises a pydantic ValidationError and returns an
    Unprocessable Entity (422) for invalid URIs.

    Test by reversing version and name in URI, thereby making it invalid.
    """
    from fastapi import status

    version, name = "1.0", "EntityName"
    response = client.get(f"/{name}/{version}", timeout=5)

    assert not response.is_success, "Invalid URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Response:\n\n{response.json()}"
