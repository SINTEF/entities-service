"""Test the service's route to retrieve entities from the core namespace."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .conftest import ClientFixture, ParameterizeGetEntities


def test_get_entity(
    parameterized_entity: ParameterizeGetEntities,
    client: ClientFixture,
    namespace: str | None,
) -> None:
    """Test the route to retrieve an entity."""
    import json

    from fastapi import status

    from entities_service.service.config import CONFIG

    url_path = namespace or ""
    url_path += f"/{parameterized_entity.version}/{parameterized_entity.name}"

    with client() as client_:
        response = client_.get(url_path, timeout=5)

    try:
        response_json = response.json()
    except json.JSONDecodeError as exc:
        pytest.fail(f"Response is not JSON: {exc}\n\nText response:\n{response.text}")

    assert (
        response.is_success
    ), f"Response: {response_json}. Request: {response.request}"
    assert response.status_code == status.HTTP_200_OK, response.json()

    # Convert SOFT5 properties' 'dims' to 'shape'
    for entity_property in parameterized_entity.entity["properties"]:
        if "dims" in entity_property:
            entity_property["shape"] = entity_property.pop("dims")

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace
    retrieved_entity = response_json
    print(retrieved_entity)
    for key, value in retrieved_entity.items():
        assert key in parameterized_entity.entity, retrieved_entity

        if key == "uri":
            assert value == (
                f"{current_namespace}"
                f"/{parameterized_entity.version}/{parameterized_entity.name}"
            ), f"key: {key}"
        elif key == "namespace":
            assert value == current_namespace, f"key: {key}"
        else:
            assert value == parameterized_entity.entity[key], f"key: {key}"


@pytest.mark.skipif(
    sys.version_info >= (3, 12),
    reason="DLite-Python does not support Python 3.12 and above.",
)
def test_get_entity_instance(
    parameterized_entity: ParameterizeGetEntities,
    client: ClientFixture,
    namespace: str | None,
) -> None:
    """Validate that we can instantiate a DLite Instance from the response"""
    from dlite import Instance

    url_path = namespace or ""
    url_path += f"/{parameterized_entity.version}/{parameterized_entity.name}"

    with client() as client_:
        response = client_.get(url_path, timeout=5)

    # Convert SOFT5 properties' 'dims' to 'shape'
    for entity_property in parameterized_entity.entity["properties"]:
        if "dims" in entity_property:
            entity_property["shape"] = entity_property.pop("dims")

    Instance.from_dict(response.json())


def test_get_entity_not_found(client: ClientFixture, namespace: str | None) -> None:
    """Test that the route returns a Not Found (404) for non existant URIs."""
    from fastapi import status

    current_namespace = f"/{namespace}" if namespace else ""

    version, name = "0.0", "NonExistantEntity"
    with client() as client_:
        response = client_.get(f"{current_namespace}/{version}/{name}", timeout=5)

    assert not response.is_success, "Non existant (valid) URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Response:\n\n{response.json()}"


def test_get_entity_invalid_uri(client: ClientFixture, namespace: str | None) -> None:
    """Test that the service raises a pydantic ValidationError and returns an
    Unprocessable Entity (422) for invalid URIs.

    Test by reversing version and name in URI, thereby making it invalid.
    """
    from fastapi import status

    current_namespace = f"/{namespace}" if namespace else ""

    version, name = "1.0", "EntityName"
    with client() as client_:
        response = client_.get(f"{current_namespace}/{name}/{version}", timeout=5)

    assert not response.is_success, "Invalid URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Response:\n\n{response.json()}"
