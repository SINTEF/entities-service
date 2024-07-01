"""Tests for `entities-service list namespaces` CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:

    from pytest_httpx import HTTPXMock
    from typer import Typer
    from typer.testing import CliRunner

pytestmark = pytest.mark.usefixtures("_mock_config_base_url")

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


def test_list_namespaces(
    live_backend: bool,
    cli: CliRunner,
    list_app: Typer,
    existing_specific_namespace: str,
    httpx_mock: HTTPXMock,
) -> None:
    """Test `entities-service list namespaces` CLI command."""
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.model_fields["base_url"].default).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    if not live_backend:
        # Mock response for the list namespaces command
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=[core_namespace, specific_namespace],
        )

    result = cli.invoke(list_app, "namespaces")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert "Namespaces:" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert core_namespace in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert specific_namespace in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


def test_list_namespaces_return_info(
    live_backend: bool,
    existing_specific_namespace: str,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test `entities-service list namespaces` CLI command called as a Python function
    with `return_info=True`."""
    from entities_service.cli.commands.list import namespaces
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.model_fields["base_url"].default).rstrip("/")
    specific_namespace = f"{core_namespace}/{existing_specific_namespace}"

    namespaces_info = [core_namespace, specific_namespace]

    if not live_backend:
        # Mock response for the list namespaces command
        httpx_mock.add_response(
            url=f"{core_namespace}/_api/namespaces",
            method="GET",
            json=namespaces_info,
        )

    result = namespaces(return_info=True)

    assert set(result) == set(namespaces_info)

    # There should be no output in this "mode"
    result = capsys.readouterr()
    assert not result.out
    assert not result.err


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

    # Mock response for the list namespaces command
    httpx_mock.add_exception(
        HTTPError(error_message),
        url=f"{str(CONFIG.base_url).rstrip('/')}/_api/namespaces",
    )

    result = cli.invoke(list_app, "namespaces")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list namespaces. HTTP exception: "
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

    # Mock response for the list namespaces command
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_api/namespaces",
        status_code=200,
        content=b"not json",
    )

    result = cli.invoke(list_app, "namespaces")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list namespaces. JSON decode error: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.skip_if_live_backend("Cannot mock invalid namespace with live backend")
def test_unsuccessful_response(
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure a proper error message is given if the response is not successful."""
    from entities_service.service.config import CONFIG

    error_message = "Bad response"
    status_code = 400

    # Mock response for the list namespaces command
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_api/namespaces",
        status_code=status_code,
        json={"detail": error_message},
    )

    result = cli.invoke(list_app, "namespaces")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list namespaces. HTTP status code: "
        f"{status_code}. Error response: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert error_message in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.skip_if_live_backend("Cannot mock invalid namespace with live backend")
def test_bade_response_format(
    cli: CliRunner,
    list_app: Typer,
    httpx_mock: HTTPXMock,
) -> None:
    """Ensure a proper error message is given if the response format is not as
    expected."""
    from entities_service.service.config import CONFIG

    # Mock response for the list namespaces command
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_api/namespaces",
        status_code=200,
        json={"bad": "response format"},
    )

    result = cli.invoke(list_app, "namespaces")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not list namespaces. Invalid response: " in result.stderr
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
    """Ensure a proper message is given if the list namespaces response is empty."""
    from entities_service.service.config import CONFIG

    if not live_backend:
        # Mock response for the list namespaces command
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_api/namespaces",
            status_code=500,
            json={"detail": "No namespaces found in the backend."},
        )

    result = cli.invoke(list_app, "namespaces")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert "No namespaces found." in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
