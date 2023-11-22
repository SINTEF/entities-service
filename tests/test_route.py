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
        assert response.json() == entity, response.json()
