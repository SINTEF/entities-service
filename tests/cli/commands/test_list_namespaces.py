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

    assert result == namespaces_info

    # There should be no output in this "mode"
    result = capsys.readouterr()
    assert not result.out
    assert not result.err
