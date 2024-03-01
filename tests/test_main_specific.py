"""Test the service's route to retrieve entities from a specific namespace."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .conftest import ClientFixture, ParameterizeGetEntities


def test_get_namespaced_entity(
    parameterized_entity: ParameterizeGetEntities,
    client: ClientFixture,
    specific_namespace: str,
) -> None:
    """Test the route to retrieve a namespaced entity."""
    from fastapi import status

    with client() as client_:
        response = client_.get(
            f"/{specific_namespace}/{parameterized_entity.version}/{parameterized_entity.name}",
            timeout=5,
        )

    assert (
        response.is_success
    ), f"Response: {response.json()}. Request: {response.request}"
    assert response.status_code == status.HTTP_200_OK, response.json()

    # Convert SOFT5 properties' 'dims' to 'shape'
    for entity_property in parameterized_entity.entity["properties"]:
        if "dims" in entity_property:
            entity_property["shape"] = entity_property.pop("dims")

    assert response.json() == parameterized_entity.entity, response.json()


@pytest.mark.skipif(
    sys.version_info >= (3, 12),
    reason="DLite-Python does not support Python 3.12 and above.",
)
def test_get_entity_instance(
    parameterized_entity: ParameterizeGetEntities,
    client: ClientFixture,
    specific_namespace: str,
) -> None:
    """Validate that we can instantiate a DLite Instance from the response"""
    from dlite import Instance

    with client() as client_:
        response = client_.get(
            f"/{specific_namespace}/{parameterized_entity.version}/{parameterized_entity.name}",
            timeout=5,
        )

    # Convert SOFT5 properties' 'dims' to 'shape'
    for entity_property in parameterized_entity.entity["properties"]:
        if "dims" in entity_property:
            entity_property["shape"] = entity_property.pop("dims")

    resolved_entity = response.json()
    assert resolved_entity == parameterized_entity.entity, resolved_entity

    Instance.from_dict(resolved_entity)


def test_get_entity_not_found(client: ClientFixture, specific_namespace: str) -> None:
    """Test that the route returns a Not Found (404) for non existant URIs."""
    from fastapi import status

    version, name = "0.0", "NonExistantEntity"
    with client() as client_:
        response = client_.get(f"/{specific_namespace}/{version}/{name}", timeout=5)

    assert not response.is_success, "Non existant (valid) URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Response:\n\n{response.json()}"


def test_get_entity_invalid_uri(client: ClientFixture, specific_namespace: str) -> None:
    """Test that the service raises a pydantic ValidationError and returns an
    Unprocessable Entity (422) for invalid URIs.

    Test by reversing version and name in URI, thereby making it invalid.
    """
    from fastapi import status

    version, name = "1.0", "EntityName"
    with client() as client_:
        response = client_.get(f"/{specific_namespace}/{name}/{version}", timeout=5)

    assert not response.is_success, "Invalid URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Response:\n\n{response.json()}"
