"""Test the service's only route to retrieve DLite/SOFT entities."""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Literal

    from .conftest import ClientFixture, GetBackendUserFixture, ParameterizeGetEntities


@pytest.fixture()
def client(
    live_backend: bool, get_backend_user: GetBackendUserFixture
) -> ClientFixture:
    """Return the test client."""
    import os

    from fastapi.testclient import TestClient
    from httpx import Client

    from dlite_entities_service.main import APP
    from dlite_entities_service.models.auth import Token
    from dlite_entities_service.service.config import CONFIG

    def _client(
        auth_role: Literal["read", "readWrite"] | None = None
    ) -> TestClient | Client:
        """Return the test client with the given authentication role."""
        if not live_backend:
            return TestClient(
                app=APP,
                base_url=str(CONFIG.base_url),
            )

        if auth_role is None:
            auth_role = "read"

        assert auth_role in ("read", "readWrite"), (
            f"Invalid authentication role {auth_role!r}. Must be either 'read' or "
            "'readWrite'."
        )

        host, port = os.getenv("ENTITY_SERVICE_HOST", "localhost"), os.getenv(
            "ENTITY_SERVICE_PORT", "8000"
        )

        base_url = f"http://{host}"

        if port:
            base_url += f":{port}"

        backend_user = get_backend_user(auth_role)

        with Client(base_url=base_url) as temp_client:
            response = temp_client.post(
                "/_auth/token",
                data={
                    "grant_type": "password",
                    "username": backend_user["username"],
                    "password": backend_user["password"],
                },
            )

        assert response.is_success, response.text
        try:
            token = Token(**response.json())
        except Exception as exc:
            raise ValueError(
                "Could not parse the response from the token endpoint. "
                f"Response:\n{response.text}"
            ) from exc

        authentication_header = {
            "Authorization": f"{token.token_type} {token.access_token}"
        }

        return Client(
            base_url=f"http://{host}:{port}",
            headers=authentication_header,
        )

    return _client


def test_get_entity(
    parameterized_entity: ParameterizeGetEntities,
    client: ClientFixture,
) -> None:
    """Test the route to retrieve a DLite/SOFT entity."""
    from fastapi import status

    with client() as client_:
        response = client_.get(
            f"/{parameterized_entity.version}/{parameterized_entity.name}", timeout=5
        )

    assert (
        response.is_success
    ), f"Response: {response.json()}. Request: {response.request}"
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert (
        resolved_entity := response.json()
    ) == parameterized_entity.entity, resolved_entity


@pytest.mark.skipif(
    sys.version_info >= (3, 12),
    reason="DLite-Python does not support Python3.12 and above.",
)
def test_get_entity_instance(
    parameterized_entity: ParameterizeGetEntities,
    client: ClientFixture,
) -> None:
    """Validate that we can instantiate a DLite Instance from the response"""
    from dlite import Instance

    with client() as client_:
        response = client_.get(
            f"/{parameterized_entity.version}/{parameterized_entity.name}", timeout=5
        )

    assert (
        resolve_entity := response.json()
    ) == parameterized_entity.entity, resolve_entity

    Instance.from_dict(resolve_entity)


def test_get_entity_not_found(client: ClientFixture) -> None:
    """Test that the route returns a Not Found (404) for non existant URIs."""
    from fastapi import status

    version, name = "0.0", "NonExistantEntity"
    with client() as client_:
        response = client_.get(f"/{version}/{name}", timeout=5)

    assert not response.is_success, "Non existant (valid) URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Response:\n\n{response.json()}"


def test_get_entity_invalid_uri(client: ClientFixture) -> None:
    """Test that the service raises a pydantic ValidationError and returns an
    Unprocessable Entity (422) for invalid URIs.

    Test by reversing version and name in URI, thereby making it invalid.
    """
    from fastapi import status

    version, name = "1.0", "EntityName"
    with client() as client_:
        response = client_.get(f"/{name}/{version}", timeout=5)

    assert not response.is_success, "Invalid URI returned an OK response!"
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Response:\n\n{response.json()}"
