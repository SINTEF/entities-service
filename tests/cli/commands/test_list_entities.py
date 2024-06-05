"""Tests for `entities-service list entities` CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Literal

    from pytest_httpx import HTTPXMock
    from typer import Typer
    from typer.testing import CliRunner

    from entities_service.service.backend.mongodb import MongoDBBackend

    from ...conftest import GetBackendUserFixture

pytestmark = pytest.mark.usefixtures("_mock_config_base_url")

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


def test_list_entities(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    existing_specific_namespace: str,
    httpx_mock: HTTPXMock,
    get_backend_user: GetBackendUserFixture,
) -> None:
    """Test `entities-service list entities` CLI command.

    If no arguments and options are provided, the command should list all entities in
    the core namespace.

    Note, this will fail if ever a set of test entities are named similarly,
    but versioned differently.
    """
    from entities_service.models import URI_REGEX, soft_entity
    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.base_url).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    backend_user = get_backend_user(auth_role="read")
    core_backend: MongoDBBackend = get_backend(
        auth_level="write",
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=None,
    )
    core_entities = [soft_entity(**entity) for entity in core_backend.search()]

    if not live_backend:
        # Mock response for listing (valid) namespaces
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=[core_namespace, specific_namespace],
        )

        # Mock response for listing entities
        # Only return entities from the core namespace, no matter the
        # "current namespace"
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/entities?namespace=",
            method="GET",
            json=[
                entity.model_dump(mode="json", by_alias=True, exclude_unset=True)
                for entity in core_entities
            ],
        )

    result = cli.invoke(list_app, "entities")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Base namespace: {core_namespace}" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    assert "Namespace" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    for entity in core_entities:
        name, version = None, None

        if entity.name and entity.version:
            name, version = entity.name, entity.version
        else:
            assert entity.uri
            match = URI_REGEX.match(str(entity.uri))
            assert match is not None
            name, version = match.group("name"), match.group("version")

        if name is None or version is None:
            pytest.fail(
                f"Name and version could not be extracted from an entity !\n{entity}"
            )

        assert f"{name}{version}" in result.stdout.replace(
            " ", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.parametrize("namespace_format", ["full", "short"])
def test_list_entities_namespace(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    existing_specific_namespace: str,
    namespace: str | None,
    httpx_mock: HTTPXMock,
    get_backend_user: GetBackendUserFixture,
    namespace_format: Literal["full", "short"],
) -> None:
    """Test `entities-service list entities` CLI command.

    With the 'NAMESPACE' argument.

    Note, this will fail if ever a set of test entities are named similarly,
    but versioned differently.
    """
    from entities_service.models import URI_REGEX, soft_entity
    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.base_url).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    print(core_namespace)

    backend_user = get_backend_user(auth_role="read")
    backend: MongoDBBackend = get_backend(
        auth_level="write",
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=namespace,
    )
    backend_entities = [soft_entity(**entity) for entity in backend.search()]

    if not live_backend:
        # Mock response for listing (valid) namespaces
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=[core_namespace, specific_namespace],
        )

        # Mock response for listing entities from the core namespace
        httpx_mock.add_response(
            url=(
                f"{core_namespace}/_api/entities"
                f"?namespace={namespace if namespace else ''}"
            ),
            method="GET",
            json=[
                entity.model_dump(mode="json", by_alias=True, exclude_unset=True)
                for entity in backend_entities
            ],
        )

    if namespace_format == "full":
        # Pass in the full namespace, e.g., `http://onto-ns.com/meta/test`
        result = cli.invoke(
            list_app, ("entities", specific_namespace if namespace else core_namespace)
        )
    else:
        # Pass in the short namespace, e.g., `test` or nothing for the core namespace
        result = cli.invoke(list_app, ("entities", namespace if namespace else ""))

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Base namespace: {core_namespace}" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if namespace:
        assert (
            f"Specific namespace: {core_namespace}/{namespace}" in result.stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    assert "Namespace" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    for entity in backend_entities:
        name, version = None, None

        if entity.name and entity.version:
            name, version = entity.name, entity.version
        else:
            assert entity.uri
            match = URI_REGEX.match(str(entity.uri))
            assert match is not None
            name, version = match.group("name"), match.group("version")

        if name is None or version is None:
            pytest.fail(
                f"Name and version could not be extracted from an entity !\n{entity}"
            )

        assert f"{name}{version}" in result.stdout.replace(
            " ", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


def test_list_entities_all_namespaces(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    existing_specific_namespace: str,
    httpx_mock: HTTPXMock,
    get_backend_user: GetBackendUserFixture,
) -> None:
    """Test `entities-service list entities` CLI command.

    With the '--all/-a' option.

    Note, this will fail if ever a set of test entities are named similarly,
    but versioned differently.
    """
    from entities_service.models import URI_REGEX, soft_entity
    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.base_url).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    backend_user = get_backend_user(auth_role="read")
    core_backend: MongoDBBackend = get_backend(
        auth_level="write",
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=None,
    )
    core_entities = [soft_entity(**entity) for entity in core_backend.search()]
    specific_backend: MongoDBBackend = get_backend(
        auth_level="write",
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=existing_specific_namespace,
    )
    specific_entities = [soft_entity(**entity) for entity in specific_backend.search()]

    if not live_backend:
        # Mock response for listing (valid) namespaces
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=[core_namespace, specific_namespace],
        )

        # Mock response for listing entities from the core namespace
        httpx_mock.add_response(
            url=(
                f"{core_namespace}/_api/entities"
                f"?namespace=&namespace={existing_specific_namespace}"
            ),
            method="GET",
            json=[
                entity.model_dump(mode="json", by_alias=True, exclude_unset=True)
                for entity in [*core_entities, *specific_entities]
            ],
        )

    result = cli.invoke(list_app, ("entities", "--all"))

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Base namespace: {core_namespace}" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    # We have multiple namespaces, so this line should not appear
    assert "Specific namespace:" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # We have multiple namespaces, so this table header should now appear
    assert "Namespace" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # Ensure number of times namespaces are listed (in short form) in the output
    # is exactly 1.
    check_namespaces = {"/": 0, existing_specific_namespace: 0}

    for entity in [*core_entities, *specific_entities]:
        short_namespace, name, version = None, None, None

        if entity.namespace and entity.name and entity.version:
            namespace, name, version = entity.namespace, entity.name, entity.version
            namespace = namespace[len(core_namespace) :]
            short_namespace = "/" if namespace in ("/", "") else namespace.lstrip("/")
        else:
            assert entity.uri
            match = URI_REGEX.match(str(entity.uri))
            assert match is not None
            short_namespace, name, version = (
                match.group("specific_namespace"),
                match.group("name"),
                match.group("version"),
            )

            if short_namespace is None:
                short_namespace = "/"

        if name is None or version is None:
            pytest.fail(
                f"Name and version could not be extracted from an entity !\n{entity}"
            )

        assert f"{name}{version}" in result.stdout.replace(
            " ", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        if f"{short_namespace}{name}{version}" in result.stdout.replace(" ", ""):
            check_namespaces[short_namespace] += 1

    assert list(check_namespaces.values()) == [1] * len(
        check_namespaces
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
