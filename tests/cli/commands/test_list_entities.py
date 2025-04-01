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
    from entities_service.service.config import CONFIG, ServiceSettings

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
    core_entities = list(core_backend)

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
                soft_entity(**entity).model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                )
                for entity in core_entities
            ],
        )

    # This will ensure the right namespace is used when testing with a live backend.
    # This (sort of) goes against the test, as we're testing calling `entities` without
    # any extra arguments or options... But this can (and will) be tested without a live
    # backend.
    command = (
        f"entities {ServiceSettings.model_fields['base_url'].default}"
        if live_backend
        else "entities"
    )

    result = cli.invoke(list_app, command)

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

        if entity.get("name") and entity.get("version"):
            name, version = entity["name"], entity["version"]
        else:
            assert entity.get("uri")
            match = URI_REGEX.match(entity["uri"])
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
    if live_backend and namespace_format == "short":
        pytest.skip("Cannot test short namespace format with a live backend.")

    from entities_service.models import URI_REGEX, soft_entity
    from entities_service.service.backend import get_backend
    from entities_service.service.config import CONFIG, ServiceSettings

    core_namespace = str(ServiceSettings.model_fields["base_url"].default).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    backend_user = get_backend_user(auth_role="read")
    backend: MongoDBBackend = get_backend(
        auth_level="write",
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=namespace,
    )
    backend_entities = list(backend)

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
                soft_entity(**entity).model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                )
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
        f"Base namespace: {str(CONFIG.base_url).rstrip('/')}" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if namespace:
        assert (
            f"Specific namespace: {str(CONFIG.base_url).rstrip('/')}/{namespace}"
            in result.stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    assert "Namespace" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    for entity in backend_entities:
        name, version = None, None

        if entity.get("name") and entity.get("version"):
            name, version = entity["name"], entity["version"]
        else:
            assert entity.get("uri")
            match = URI_REGEX.match(entity["uri"])
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
    from entities_service.service.config import CONFIG, ServiceSettings

    core_namespace = str(ServiceSettings.model_fields["base_url"].default).rstrip("/")
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
    core_entities = list(core_backend)
    specific_backend: MongoDBBackend = get_backend(
        auth_level="write",
        settings={
            "mongo_username": backend_user["username"],
            "mongo_password": backend_user["password"],
        },
        db=existing_specific_namespace,
    )
    specific_entities = list(specific_backend)

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
                soft_entity(**entity).model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                )
                for entity in [*core_entities, *specific_entities]
            ],
        )

    result = cli.invoke(list_app, ("entities", "--all"))

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Base namespace: {str(CONFIG.base_url).rstrip('/')}" in result.stdout
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

        if entity.get("namespace") and entity.get("name") and entity.get("version"):
            namespace, name, version = (
                entity["namespace"],
                entity["name"],
                entity["version"],
            )
            namespace = namespace[len(core_namespace) :]
            short_namespace = "/" if namespace in ("/", "") else namespace.lstrip("/")
        else:
            assert entity.get("uri")
            match = URI_REGEX.match(entity["uri"])
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


def test_unparseable_namespace(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test `entities-service list entities` CLI command.

    With a namespace that results in a raised ValueError when calling
    `_parse_namespace()`.
    """
    from entities_service.service.config import ServiceSettings

    bad_namespace = "bad_namespace"
    error_message = "Invalid namespace"

    core_namespace = str(ServiceSettings.model_fields["base_url"].default).rstrip("/")

    if not live_backend:
        # Mock response for listing (valid) namespaces
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=[core_namespace],
        )

    # Monkeypatch the `_parse_namespace()` function to raise a ValueError
    def _raise_valueerror(namespace, allow_external=True) -> str:  # noqa: ARG001
        raise ValueError(error_message)

    monkeypatch.setattr(
        "entities_service.cli.commands.list._parse_namespace", _raise_valueerror
    )

    result = cli.invoke(list_app, ("entities", bad_namespace))

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Error: Cannot parse one or more namespaces. Error message: {error_message}"
        in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


def test_invalid_namespace(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
    existing_specific_namespace: str,
) -> None:
    """Test `entities-service list entities` CLI command.

    With an invalid namespace.
    """
    from entities_service.service.config import CONFIG, ServiceSettings

    non_existing_namespace = "non_existing_namespace"

    core_namespace = str(ServiceSettings.model_fields["base_url"].default).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"
    valid_namespaces = sorted([core_namespace, specific_namespace])

    if not live_backend:
        # Mock response for listing (valid) namespaces
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=valid_namespaces,
        )

    result = cli.invoke(list_app, ("entities", non_existing_namespace))

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Invalid namespace(s) given: "
        f"{[str(CONFIG.base_url).rstrip('/') + '/' + non_existing_namespace]}"
        f"Valid namespaces: {valid_namespaces}" in result.stderr.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.skip_if_live_backend("Cannot mock HTTP error with live backend")
def test_http_errors(
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure the proper error message is given if an HTTP error occurs."""
    from httpx import HTTPError

    from entities_service.service.config import CONFIG

    error_message = "Generic HTTP Error"

    core_namespace = str(CONFIG.base_url).rstrip("/")

    # Mock response for listing (valid) namespaces
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/namespaces",
        method="GET",
        json=[core_namespace],
    )

    # Mock response for the list namespaces command
    httpx_mock.add_exception(
        HTTPError(error_message),
        url=f"{core_namespace}/_api/entities?namespace=",
    )

    result = cli.invoke(list_app, "entities")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list entities. HTTP exception: "
        f"{error_message}" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.skip_if_live_backend("Cannot mock JSON decode error with live backend")
def test_json_decode_errors(
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure a proper error message is given if a JSONDecodeError occurs."""
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.base_url).rstrip("/")

    # Mock response for listing (valid) namespaces
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/namespaces",
        method="GET",
        json=[core_namespace],
    )

    # Mock response for the list namespaces command
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/entities?namespace=",
        status_code=200,
        content=b"not json",
    )

    result = cli.invoke(list_app, "entities")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list entities. JSON decode error: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.skip_if_live_backend("Cannot mock invalid response with live backend")
def test_unsuccessful_response(
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure a proper error message is given if the response is not successful."""
    from entities_service.service.config import CONFIG

    error_message = "Bad response"
    status_code = 400

    core_namespace = str(CONFIG.base_url).rstrip("/")

    # Mock response for listing (valid) namespaces
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/namespaces",
        method="GET",
        json=[core_namespace],
    )

    # Mock response for the list namespaces command
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/entities?namespace=",
        status_code=status_code,
        json={"detail": error_message},
    )

    result = cli.invoke(list_app, "entities")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list entities. HTTP status code: "
        f"{status_code}. Error response: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert error_message in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.skip_if_live_backend(
    "Cannot mock invalid response format with live backend"
)
def test_bad_response_format(
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure a proper error message is given if the response format is not as
    expected."""
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.base_url).rstrip("/")

    # Mock response for listing (valid) namespaces
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/namespaces",
        method="GET",
        json=[core_namespace],
    )

    # Mock response for the list namespaces command
    httpx_mock.add_response(
        url=f"{core_namespace}/_api/entities?namespace=",
        status_code=200,
        json={"bad": "response format"},  # should be a list of dicts
    )

    result = cli.invoke(list_app, "entities")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list entities. Invalid response: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.usefixtures("_empty_backend_collection")
def test_empty_list_response(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure a proper message is given if the list entities response is empty."""
    from entities_service.service.config import ServiceSettings

    core_namespace = str(ServiceSettings.model_fields["base_url"].default).rstrip("/")

    if not live_backend:
        # Mock response for listing (valid) namespaces
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=[core_namespace],
        )

        # Mock response for the list namespaces command
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/entities?namespace=",
            status_code=200,
            json=[],
        )

    result = cli.invoke(list_app, "entities")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "No entities found in namespace(s) " in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
