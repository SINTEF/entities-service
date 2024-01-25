"""Tests for `entities-service login` CLI command."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal

    from pytest_httpx import HTTPXMock
    from typer.testing import CliRunner

    from ..conftest import GetBackendUserFixture, ParameterizeGetEntities


CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


@pytest.mark.parametrize("input_method", ["cli_option", "stdin", "env"])
def test_login(
    cli: CliRunner,
    input_method: Literal["cli_option", "stdin"],
    httpx_mock: HTTPXMock,
    get_backend_user: GetBackendUserFixture,
    live_backend: bool,
    token_mock: str,
) -> None:
    """Test the `entities-service login` CLI command."""
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    backend_user = get_backend_user()

    username = backend_user["username"]
    password = backend_user["password"]

    if not live_backend:
        # Mock the HTTPX response
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_auth/token",
            method="POST",
            match_content=f"grant_type=password&username={username}&password={password}".encode(),
            json={"access_token": token_mock},
        )

        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/users/me",
            match_headers={"Authorization": f"Bearer {token_mock}"},
            json={
                "username": username,
                "full_name": backend_user["full_name"],
                "roles": backend_user["roles"],
            },
        )

    # Run the CLI command
    if input_method == "cli_option":
        result = cli.invoke(
            APP,
            f"login --username {username} --password {password}",
            catch_exceptions=False,
        )
    elif input_method == "stdin":
        result = cli.invoke(
            APP,
            "login",
            input=f"{username}\n{password}\n",
            env={"ENTITY_SERVICE_ADMIN_USER": "", "ENTITY_SERVICE_ADMIN_PASSWORD": ""},
        )
    elif input_method == "env":
        result = cli.invoke(
            APP,
            "login",
            env={
                "ENTITY_SERVICE_ADMIN_USER": username,
                "ENTITY_SERVICE_ADMIN_PASSWORD": password,
            },
        )

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Successfully logged in." in result.stdout.replace("\n", "")

    if input_method == "stdin":
        assert "Username: " in result.stdout
        assert "Password: " in result.stdout


@pytest.mark.usefixtures("_empty_backend_collection")
def test_token_persistence(
    cli: CliRunner,
    httpx_mock: HTTPXMock,
    static_dir: Path,
    parameterized_entity: ParameterizeGetEntities,
    get_backend_user: GetBackendUserFixture,
    live_backend: bool,
    tmp_path: Path,
    request: pytest.FixtureRequest,
    token_mock: str,
) -> None:
    """Test that the token is persisted to the config file."""
    import traceback

    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    backend_user = get_backend_user(auth_role="readWrite")

    username = backend_user["username"]
    password = backend_user["password"]

    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    if not live_backend:
        # Mock the login HTTPX response
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_auth/token",
            method="POST",
            match_content=f"grant_type=password&username={username}&password={password}".encode(),
            json={"access_token": token_mock},
        )

        # Mock response for "Create entities"
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
            method="POST",
            match_headers={"Authorization": f"Bearer {token_mock}"},
            match_json=[parameterized_entity.backend_entity],
            status_code=201,  # created
        )

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=parameterized_entity.uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )

    # Run the upload CLI command - ensuring an error is raised due to the missing token
    result = cli.invoke(APP, f"upload --file {test_file}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    ) + (
        "\n\nEXCEPTION:\n"
        f"{''.join(traceback.format_exception(result.exception)) if result.exception else ''}"  # noqa: E501
    )
    assert (
        "Error: Missing authorization token. Please login first by running "
        "'entities-service login'." in result.stderr.replace("\n", "")
    )
    if "[test_client]" not in request.node.name:
        assert not result.stdout

    # Run the login CLI command
    result = cli.invoke(
        APP,
        f"login --username {username} --password {password}",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    ) + (
        "\n\nEXCEPTION:\n"
        f"{''.join(traceback.format_exception(result.exception)) if result.exception else ''}"  # noqa: E501
    )
    assert "Successfully logged in." in result.stdout.replace("\n", "")

    # Run the upload command again
    result = cli.invoke(APP, f"upload --file {test_file}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    ) + (
        "\n\nEXCEPTION:\n"
        f"{''.join(traceback.format_exception(result.exception)) if result.exception else ''}"  # noqa: E501
    )
    assert "Successfully uploaded 1 entity:" in result.stdout.replace("\n", "")
    assert not result.stderr


def test_login_invalid_credentials(
    cli: CliRunner,
    httpx_mock: HTTPXMock,
    get_backend_user: GetBackendUserFixture,
    live_backend: bool,
    request: pytest.FixtureRequest,
) -> None:
    """Test that the command fails with invalid credentials."""
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    username = "testuser"
    password = "testpassword"

    # Ensure the test credentials are not the same as the ones used for the backend
    for auth_role in ["read", "readWrite"]:
        assert (
            username != get_backend_user(auth_role=auth_role)["username"]
            or password != get_backend_user(auth_role=auth_role)["password"]
        )

    if not live_backend:
        # Mock the HTTPX response
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_auth/token",
            method="POST",
            match_content=f"grant_type=password&username={username}&password={password}".encode(),
            status_code=401,  # unauthorized
            headers={"WWW-Authenticate": "Bearer"},
            json={"detail": "Incorrect username or password"},
        )

    # Run the CLI command
    result = cli.invoke(APP, f"login --username {username} --password {password}")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Error: Could not login. HTTP status code: 401. Error message: "
        "{'detail': 'Incorrect username or password'}"
        in result.stderr.replace("\n", "")
    )
    if "[test_client]" not in request.node.name:
        assert not result.stdout


@pytest.mark.skip_if_live_backend("Does not raise HTTP errors in this case.")
def test_http_errors(cli: CliRunner, httpx_mock: HTTPXMock) -> None:
    """Ensure proper error messages are given if an HTTP error occurs."""
    from httpx import HTTPError

    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    username = "testuser"
    password = "testpassword"

    error_message = "Generic HTTP error"

    # Mock the login HTTPX response
    httpx_mock.add_exception(
        HTTPError(error_message),
        url=f"{str(CONFIG.base_url).rstrip('/')}/_auth/token",
        method="POST",
        match_content=f"grant_type=password&username={username}&password={password}".encode(),
    )

    # Run the login CLI command
    result = cli.invoke(APP, f"login --username {username} --password {password}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        f"Error: Could not login. HTTP exception: {error_message}"
        in result.stderr.replace("\n", "")
    )
    assert not result.stdout


@pytest.mark.parametrize(
    "return_status_code", [200, 500], ids=["OK", "Internal Server Error"]
)
@pytest.mark.skip_if_live_backend("Does not raise JSON decode errors in this case.")
def test_json_decode_errors(
    cli: CliRunner, httpx_mock: HTTPXMock, return_status_code: Literal[200, 500]
) -> None:
    """Ensure proper error messages are given if a JSON decode error occurs."""
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    username = "testuser"
    password = "testpassword"

    # Mock the login HTTPX response
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_auth/token",
        method="POST",
        match_content=f"grant_type=password&username={username}&password={password}".encode(),
        status_code=return_status_code,
        content=b"invalid json",
    )

    # Run the login CLI command
    result = cli.invoke(APP, f"login --username {username} --password {password}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Error: Could not login. JSON decode error: " in result.stderr.replace(
        "\n", ""
    )
    assert not result.stdout


@pytest.mark.skip_if_live_backend(
    "Does not raise pydantic.ValidationErrors in this case."
)
def test_validation_error(cli: CliRunner, httpx_mock: HTTPXMock) -> None:
    """Ensure proper error messages are given if the response cannot be parsed as a
    valid token."""
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    username = "testuser"
    password = "testpassword"

    # Mock the login HTTPX response
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_auth/token",
        method="POST",
        match_content=f"grant_type=password&username={username}&password={password}".encode(),
        status_code=200,
        json={"invalid_token_key": "invalid_token_value"},
    )

    # Run the login CLI command
    result = cli.invoke(APP, f"login --username {username} --password {password}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Error: Could not login. Validation error: " in result.stderr.replace(
        "\n", ""
    )
    assert not result.stdout
