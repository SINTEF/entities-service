"""Tests for `entities-service login` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock
    from typer.testing import CliRunner

    from .conftest import ParameterizeGetEntities

pytestmark = [
    pytest.mark.skip_if_live_backend("OAuth2 verification cannot be mocked."),
    pytest.mark.httpx_mock(can_send_already_matched_responses=True),
]

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_login(
    cli: CliRunner,
    httpx_mock: HTTPXMock,
) -> None:
    """Test the `entities-service login` CLI command."""
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_json=[],
        status_code=204,  # no content
    )

    # Run the CLI command
    result = cli.invoke(APP, "login")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Successfully logged in." in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_empty_backend_collection", "_mock_successful_oauth_response")
def test_token_persistence(
    cli: CliRunner,
    httpx_mock: HTTPXMock,
    static_dir: Path,
    parameterized_entity: ParameterizeGetEntities,
    tmp_cache_file: Path,
    token_mock: str,
) -> None:
    """Test that the token is persisted to the config file."""
    import traceback

    from httpx_auth import JsonTokenFileCache, OAuth2

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    assert isinstance(OAuth2.token_cache, JsonTokenFileCache)
    assert str(OAuth2.token_cache._tokens_path) == str(tmp_cache_file)
    OAuth2.token_cache.clear()

    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    # Mock the authorization check response
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_json=[],
        status_code=204,  # no content
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

    assert not tmp_cache_file.exists()

    # Run the upload command
    result = cli.invoke(APP, f"upload {test_file}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    ) + (
        "\n\nEXCEPTION:\n"
        f"{''.join(traceback.format_exception(result.exception)) if result.exception else ''}"  # noqa: E501
    )
    assert "Successfully uploaded 1 entity" in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert tmp_cache_file.exists()


@pytest.mark.usefixtures("_mock_failed_oauth_response")
def test_login_invalid_credentials(
    cli: CliRunner,
    request: pytest.FixtureRequest,
) -> None:
    """Test that the command fails with invalid credentials."""
    from entities_service.cli.main import APP

    # Run the CLI command
    result = cli.invoke(APP, "login")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Error: Could not login. Authentication failed (InvalidGrantRequest): "
        "temporarily_unavailable" in result.stderr.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    if "[test_client]" not in request.node.name:
        assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_http_errors(cli: CliRunner, httpx_mock: HTTPXMock) -> None:
    """Ensure proper error messages are given if an HTTP error occurs."""
    from httpx import HTTPError

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    error_message = "Generic HTTP error"

    # Mock the login HTTPX response
    httpx_mock.add_exception(
        HTTPError(error_message),
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_json=[],
    )

    # Run the login CLI command
    result = cli.invoke(APP, "login")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        f"Error: Could not login. HTTP exception: {error_message}"
        in result.stderr.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_json_decode_errors(cli: CliRunner, httpx_mock: HTTPXMock) -> None:
    """Ensure proper error messages are given if a JSON decode error occurs."""
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    # Mock the login HTTPX response
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        status_code=500,
        content=b"invalid json",
    )

    # Run the login CLI command
    result = cli.invoke(APP, "login")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Error: Could not login. JSON decode error: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    ## Re-mock the response for "Get token" to be bad JSON
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/oauth/token",
        method="POST",
        text="access_token",
    )

    # Run the login CLI command
    result = cli.invoke(APP, "login")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Error: Could not login. JSON decode error: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_bad_response(cli: CliRunner, httpx_mock: HTTPXMock) -> None:
    """Ensure proper error messages are given if an HTTP error occurs."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    error_status_code = 500
    error_message = {"error": "Internal Server Error"}

    # Mock the login HTTPX response
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_json=[],
        status_code=error_status_code,
        json=error_message,
    )

    # Run the login CLI command
    result = cli.invoke(APP, "login")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        f"Error: Could not login. HTTP status code: {error_status_code}. "
        f"Error response: {json.dumps(error_message)}"
    ) in result.stderr.replace("\n", "").replace(
        "  ", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
