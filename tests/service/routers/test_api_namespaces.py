"""Test the /_api/namespaces endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from ...conftest import ClientFixture, GetBackendUserFixture


def test_list_namespaces(client: ClientFixture) -> None:
    """Test calling the endpoint straight up."""
    from entities_service.service.config import ServiceSettings

    # List namespaces
    with client() as client_:
        response = client_.get("/_api/namespaces")

    response_json = response.json()

    expected_response = [
        str(ServiceSettings.model_fields["base_url"].default).rstrip("/")
        + specific_namespace
        for specific_namespace in ("", "/test")
    ]

    # Check response
    assert response.status_code == 200, response_json
    assert isinstance(response_json, list), response_json
    assert set(response_json) == set(expected_response), response_json


@pytest.mark.usefixtures("_empty_backend_collection")
def test_empty_dbs(client: ClientFixture) -> None:
    """Test calling the endpoint with no or empty backend databases."""
    # List namespaces
    with client() as client_:
        response = client_.get("/_api/namespaces")

    response_json = response.json()

    expected_response = {"detail": "No namespaces found in the backend."}

    # Check response
    assert response.status_code == 500, response_json
    assert isinstance(response_json, dict), response_json
    assert response_json == expected_response, response_json


@pytest.mark.usefixtures("_empty_backend_collection")
def test_namespace_from_entity_namespace(
    client: ClientFixture,
    static_dir: Path,
    get_backend_user: GetBackendUserFixture,
) -> None:
    """Test retrieving the namespace from an entity's 'namespace' attribute."""
    import yaml

    from entities_service.service.backend import get_backend
    from entities_service.service.config import ServiceSettings

    entity: dict[str, Any] | None = None
    entities: list[dict[str, Any]] = yaml.safe_load(
        (static_dir / "valid_entities.yaml").read_text()
    )

    for entity in entities:
        if "namespace" in entity:
            break
    else:
        pytest.fails(
            "No entity with the 'namespace' attribute found in 'valid_entities.yaml'."
        )

    assert entity is not None

    # Ensure namespace is the core namespace
    entity["namespace"] = str(ServiceSettings.model_fields["base_url"].default).rstrip(
        "/"
    )

    # Remove uri/identity if it exists
    entity.pop("uri", entity.pop("identity", None))

    # Add entity with 'namespace' attribute (and not 'uri')
    backend_user = get_backend_user(auth_role="write")
    backend = get_backend(
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        }
    )
    backend.create([entity])

    # List namespaces
    with client() as client_:
        response = client_.get("/_api/namespaces")

    response_json = response.json()

    # Check response
    assert response.status_code == 200, response_json
    assert isinstance(response_json, list), response_json
    assert response_json == [entity["namespace"]], response_json
