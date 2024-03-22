"""Test the /_admin/* endpoints.

For now there is only a single endpoint under /_admin, namely /_admin/create.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

    from entities_service.service.backend.mongodb import MongoDBBackend

    from ...conftest import (
        ClientFixture,
        GetBackendUserFixture,
        MockAuthVerification,
        ParameterizeGetEntities,
    )


pytestmark = pytest.mark.skip_if_live_backend("OAuth2 verification cannot be mocked.")


def test_create_single_entity(
    client: ClientFixture,
    parameterized_entity: ParameterizeGetEntities,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
    namespace: str | None,
) -> None:
    """Test creating a single entity."""
    from copy import deepcopy

    from entities_service.service.config import CONFIG

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    entity = deepcopy(parameterized_entity.entity)

    if namespace:
        core_namespace = str(CONFIG.base_url).rstrip("/")
        current_namespace = f"{core_namespace}/{namespace}"

        # Update namespace in entity
        if "namespace" in entity:
            entity["namespace"] = current_namespace

        id_key = "uri" if "uri" in entity else "identity"
        if id_key in entity:
            entity[id_key] = entity[id_key].replace(core_namespace, current_namespace)

    # Create single entity
    with client(auth_role="write") as client_:
        response = client_.post(
            "/_admin/create",
            json=entity,
            headers=auth_header,
        )

    response_json = response.json()

    # Update entity according to the expected response
    if "identity" in entity:
        entity["uri"] = entity.pop("identity")

    # Check response
    assert response.status_code == 201, response_json
    assert isinstance(response_json, dict), response_json
    assert response_json == entity, response_json


def test_create_multiple_entities(
    static_dir: Path,
    client: ClientFixture,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
    existing_specific_namespace: str,
    get_backend_user: GetBackendUserFixture,
) -> None:
    """Test creating multiple entities."""

    import yaml

    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    # Load entities
    entities: list[dict[str, Any]] = yaml.safe_load(
        (static_dir / "valid_entities.yaml").read_text()
    )
    original_length = len(entities)

    # Add specific namespace entities
    core_namespace = str(CONFIG.base_url).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    for entity in list(entities):
        id_key = "uri" if "uri" in entity else "identity"
        if id_key in entity:
            entity[id_key] = entity[id_key].replace(core_namespace, specific_namespace)

        if "namespace" in entity:
            entity["namespace"] = specific_namespace

        entities.append(entity)

    # Create multiple entities
    with client(auth_role="write") as client_:
        response = client_.post(
            "/_admin/create",
            json=entities,
            headers=auth_header,
        )

    response_json = response.json()

    # Update entities according to the expected response
    for entity in entities:
        if "identity" in entity:
            entity["uri"] = entity.pop("identity")

    # Check response
    assert response.status_code == 201, response_json
    assert isinstance(response_json, list), response_json
    assert response_json == entities, response_json
    assert len(response_json) == 2 * original_length, response_json

    # Check they can be retrieved
    for entity in entities:
        uri = entity.get("uri", entity.get("identity", None)) or (
            f"{entity.get('namespace', '')}/{entity.get('version', '')}"
            f"/{entity.get('name', '')}"
        )
        test_url = uri[len(core_namespace) :]
        with client() as client_:
            response = client_.get(test_url, timeout=5)

        assert (
            response.is_success
        ), f"Response: {response.json()}. Request: {response.request}"
        assert response.status_code == 200, response.json()
        assert response.json() == entity, response.json()

    # Check the entities exist in separate MongoDB collections
    backend_user = get_backend_user()
    core_backend = get_backend(
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        }
    )
    specific_backend = get_backend(
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=existing_specific_namespace,
    )
    for entity in entities:
        uri = entity.get("uri", entity.get("identity", None)) or (
            f"{entity.get('namespace', '')}/{entity.get('version', '')}"
            f"/{entity.get('name', '')}"
        )

        # Match the entity with how they are stored in the backend (MongoDB)
        # SOFT5 style
        if isinstance(entity.get("properties", None), list):
            entity["properties"] = [
                {key.replace("$ref", "ref"): value for key, value in property_.items()}
                for property_ in entity["properties"]
            ]
        # SOFT7 style
        elif isinstance(entity.get("properties", None), dict):
            for property_name, property_value in list(entity["properties"].items()):
                entity["properties"][property_name] = {
                    key.replace("$ref", "ref"): value
                    for key, value in property_value.items()
                }
        else:
            pytest.fail("Invalid entity: {entity}")

        if uri.startswith(specific_namespace):
            assert specific_backend.read(uri) == entity, (
                f"uri={uri} collection={specific_backend._collection.name} "
                f"entity={entity}"
            )
            assert (
                core_backend.read(uri) is None
            ), f"uri={uri} collection={core_backend._collection.name} entity={entity}"
        else:
            assert specific_backend.read(uri) is None, (
                f"uri={uri} collection={specific_backend._collection.name} "
                f"entity={entity}"
            )
            assert (
                core_backend.read(uri) == entity
            ), f"uri={uri} collection={core_backend._collection.name} entity={entity}"


def test_create_no_entities(
    client: ClientFixture,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
) -> None:
    """Test creating no entities."""
    from json import JSONDecodeError

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    # Create no entities
    with client(auth_role="write") as client_:
        response = client_.post(
            "/_admin/create",
            json=[],
            headers=auth_header,
        )

    # Check response
    assert response.content == b"", response.content
    assert response.status_code == 204, response.content

    with pytest.raises(JSONDecodeError):
        response.json()


def test_create_invalid_entity(
    static_dir: Path,
    client: ClientFixture,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
) -> None:
    """Test creating an invalid entity."""
    import json

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    # Load invalid entities
    entities: list[dict[str, Any]] = [
        json.loads(invalid_entity_file.read_text())
        for invalid_entity_file in (static_dir / "invalid_entities").glob("*.json")
    ]

    # Create multiple invalid entities
    with client(auth_role="write", raise_server_exceptions=False) as client_:
        response = client_.post(
            "/_admin/create",
            json=entities,
            headers=auth_header,
        )

    response_json = response.json()

    # Check response
    assert response.status_code == 422, response_json
    assert isinstance(response_json, dict), response_json
    assert "detail" in response_json, response_json

    # Create single invalid entities
    for entity in entities:
        uri = entity.get("uri", entity.get("identity", None)) or (
            f"{entity.get('namespace', '')}/{entity.get('version', '')}"
            f"/{entity.get('name', '')}"
        )
        error_message = f"Failed to create entity with uri {uri}"

        with client(auth_role="write", raise_server_exceptions=False) as client_:
            response = client_.post(
                "/_admin/create",
                json=entity,
                headers=auth_header,
            )

        response_json = response.json()

        # Check response
        assert response.status_code == 422, f"{error_message}\n{response_json}"
        assert isinstance(response_json, dict), f"{error_message}\n{response_json}"
        assert "detail" in response_json, f"{error_message}\n{response_json}"


def test_user_with_no_write_access(
    static_dir: Path,
    client: ClientFixture,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
) -> None:
    """Test that a 401 exception is raised if the user does not have write access."""
    import yaml

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="read")

    # Load entities
    entities = yaml.safe_load((static_dir / "valid_entities.yaml").read_text())

    # Create single entity
    with client(auth_role="read") as client_:
        response = client_.post(
            "/_admin/create",
            json=entities,
            headers=auth_header,
        )

    response_json = response.json()

    # Check response
    assert response.status_code == 403, response_json
    assert isinstance(response_json, dict), response_json
    assert "detail" in response_json, response_json
    assert response_json["detail"] == (
        "You do not have the rights to create entities. "
        "Please contact the entities-service group maintainer."
    ), response_json
    assert "WWW-Authenticate" in response.headers, response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer", response.headers[
        "WWW-Authenticate"
    ]


def test_backend_write_error_exception(
    static_dir: Path,
    client: ClientFixture,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a 502 exception is raised if the backend cannot write the entity."""
    import yaml

    # Monkeypatch the backend create method to raise an exception
    from entities_service.service.backend import mongodb as entities_backend

    def mock_create(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
        raise entities_backend.MongoDBBackendError("Test error.")

    monkeypatch.setattr(entities_backend.MongoDBBackend, "create", mock_create)

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    # Load entities
    entities = yaml.safe_load((static_dir / "valid_entities.yaml").read_text())

    # Create single entity
    with client(auth_role="write", raise_server_exceptions=False) as client_:
        response = client_.post(
            "/_admin/create",
            json=entities,
            headers=auth_header,
        )

    response_json = response.json()

    # Check response
    assert response.status_code == 502, response_json
    assert isinstance(response_json, dict), response_json
    assert "detail" in response_json, response_json
    assert response_json["detail"] == (
        "Could not create entities with uris: "
        f"{', '.join(entity.get('uri', entity.get('identity')) for entity in entities)}"
    ), response_json


def test_backend_create_returns_bad_value(
    client: ClientFixture,
    parameterized_entity: ParameterizeGetEntities,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that an exception is raised if the backend's create methods returns a bad
    value.

    Using the `parameterized_entity` fixture, to test the error response detail changes
    from the response checked in the `test_backend_write_error_exception` test.
    """
    # Monkeypatch the backend create method to return an unexpected value
    monkeypatch.setattr(
        "entities_service.service.backend.mongodb.MongoDBBackend.create",
        lambda *args, **kwargs: None,  # noqa: ARG005
    )

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    # Create single entity
    with client(auth_role="write") as client_:
        response = client_.post(
            "/_admin/create",
            json=parameterized_entity.entity,
            headers=auth_header,
        )

    response_json = response.json()

    # Check response
    assert response.status_code == 502, response_json
    assert isinstance(response_json, dict), response_json
    assert "detail" in response_json, response_json
    assert (
        response_json["detail"]
        == f"Could not create entity with uri: {parameterized_entity.uri}"
    ), response_json


def test_create_entity_in_new_namespace(
    client: ClientFixture,
    parameterized_entity: ParameterizeGetEntities,
    mock_auth_verification: MockAuthVerification,
    auth_header: dict[Literal["Authorization"], str],
    existing_specific_namespace: str,
    get_backend_user: GetBackendUserFixture,
) -> None:
    """Test creating an entity in a previously non-existent specific namespace."""
    from copy import deepcopy

    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG

    # Setup mock responses for OAuth2 verification
    mock_auth_verification(auth_role="write")

    entity = deepcopy(parameterized_entity.entity)

    # New namespace. First: (`.`|`-`) > `_` and then `/` > `.`
    namespace = f"main/sub.namespace-{parameterized_entity.name}"
    backend_namespace = (
        "main.sub_namespace_"
        f"{parameterized_entity.name.replace('-', '_').replace('.', '_').replace('/', '.')}"  # noqa: E501
    )

    assert namespace != existing_specific_namespace
    assert backend_namespace != existing_specific_namespace

    # Update entity
    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}"

    # Update namespace in entity
    if "namespace" in entity:
        entity["namespace"] = current_namespace

    id_key = "uri" if "uri" in entity else "identity"
    if id_key in entity:
        entity[id_key] = entity[id_key].replace(core_namespace, current_namespace)

    # Create expected entity
    expected_entity = deepcopy(entity)

    if "identity" in expected_entity:
        expected_entity["uri"] = expected_entity.pop("identity")

    # Ensure the backend does not exist
    backend_user = get_backend_user()
    new_backend: MongoDBBackend = get_backend(
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=namespace,
    )
    current_collections = new_backend._collection.database.list_collection_names()
    assert backend_namespace not in current_collections
    assert namespace not in current_collections

    # Create entity
    with client(auth_role="write") as client_:
        response = client_.post(
            "/_admin/create",
            json=entity,
            headers=auth_header,
        )

    response_json = response.json()

    # Check response
    assert response.status_code == 201, response_json
    assert isinstance(response_json, dict), response_json
    assert response_json == expected_entity, response_json

    # Check backend
    current_collections = new_backend._collection.database.list_collection_names()
    assert backend_namespace in current_collections
    assert namespace not in current_collections
