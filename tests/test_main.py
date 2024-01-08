"""Test the service's only route to retrieve DLite/SOFT entities."""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NamedTuple

import pytest

if TYPE_CHECKING:
    from typing import Any

    from .conftest import ClientFixture


class ParameterizeGetEntities(NamedTuple):
    """Returned tuple from parameterizing all entities."""

    entity: dict[str, Any]
    version: str
    name: str


def parameterize_get_entities() -> list[ParameterizeGetEntities]:
    """Parameterize the test to retrieve all entities."""
    from pathlib import Path

    import yaml

    def get_version_name(uri: str) -> tuple[str, str]:
        """Return the version and name part of a uri."""
        import re

        from dlite_entities_service.service.config import CONFIG

        namespace = str(CONFIG.base_url).rstrip("/")

        match = re.match(
            rf"^{re.escape(namespace)}/(?P<version>[^/]+)/(?P<name>[^/]+)$", uri
        )
        assert match is not None, (
            f"Could not retrieve version and name from {uri!r}. "
            "URI must be of the form: "
            f"{namespace}/{{version}}/{{name}}\n\n"
            "Hint: Did you (inadvertently) set the base_url to something?"
        )

        return match.group("version") or "", match.group("name") or ""

    def get_uri(entity: dict[str, Any]) -> str:
        """Return the uri for an entity."""
        namespace = entity.get("namespace")
        version = entity.get("version")
        name = entity.get("name")

        assert not any(
            _ is None for _ in (namespace, version, name)
        ), "Could not retrieve namespace, version, and/or name from test entities."

        return f"{namespace}/{version}/{name}"

    static_dir = (Path(__file__).parent / "static").resolve()

    results: list[ParameterizeGetEntities] = []

    entities: list[dict[str, Any]] = yaml.safe_load(
        (static_dir / "entities.yaml").read_text()
    )

    for entity in entities:
        uri = entity.get("uri") or get_uri(entity)

        version, name = get_version_name(uri)

        results.append(ParameterizeGetEntities(entity, version, name))

    return results


@pytest.mark.parametrize(
    ("entity", "version", "name"),
    parameterize_get_entities(),
    ids=[f"{_.version}/{_.name}" for _ in parameterize_get_entities()],
)
def test_get_entity(
    entity: dict[str, Any],
    version: str,
    name: str,
    client: ClientFixture,
) -> None:
    """Test the route to retrieve a DLite/SOFT entity."""
    from fastapi import status

    with client() as client_:
        response = client_.get(f"/{version}/{name}", timeout=5)

    assert (
        response.is_success
    ), f"Response: {response.json()}. Request: {response.request}"
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert (resolved_entity := response.json()) == entity, resolved_entity


@pytest.mark.skipif(
    sys.version_info >= (3, 12),
    reason="DLite-Python does not support Python3.12 and above.",
)
@pytest.mark.parametrize(
    ("entity", "version", "name"),
    parameterize_get_entities(),
    ids=[f"{_.version}/{_.name}" for _ in parameterize_get_entities()],
)
def test_get_entity_instance(
    entity: dict[str, Any],
    version: str,
    name: str,
    client: ClientFixture,
) -> None:
    """Validate that we can instantiate a DLite Instance from the response"""
    from dlite import Instance

    with client() as client_:
        response = client_.get(f"/{version}/{name}", timeout=5)

    assert (resolve_entity := response.json()) == entity, resolve_entity

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
