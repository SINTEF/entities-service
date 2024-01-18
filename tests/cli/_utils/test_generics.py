"""Test CLI generics utility module."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal

    from pytest_httpx import HTTPXMock


@pytest.mark.parametrize("token_py_type", ["str", "Token"])
@pytest.mark.parametrize("invalidity_reason", ["invalid", "error"])
def test_set_and_get_cached_access_token(
    tmp_path: Path,
    token_py_type: Literal["str", "Token"],
    invalidity_reason: Literal["invalid", "error"],
    httpx_mock: HTTPXMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the cached access token can be retrieved."""
    from httpx import HTTPError

    from dlite_entities_service.cli._utils.generics import (
        cache_access_token,
        get_cached_access_token,
    )
    from dlite_entities_service.models.auth import Token
    from dlite_entities_service.service.config import CONFIG

    access_token = "test"

    token = (
        Token(access_token=access_token) if token_py_type == "Token" else access_token
    )
    as_token_model = token if isinstance(token, Token) else Token(access_token=token)

    cached_access_token_file = tmp_path / ".cache" / "access_token"

    # Ensure there is no cached access token at this point
    assert not cached_access_token_file.exists()
    assert get_cached_access_token() is None

    # Set the cached access token
    cache_access_token(token)

    # Ensure the cached access token is set correctly
    assert cached_access_token_file.exists()
    assert cached_access_token_file.read_text() == access_token

    # Ensure the cached access token can be retrieved
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/users/me",
        match_headers={
            "Authorization": (
                f"{Token.model_fields['token_type'].default} {access_token}"
            ),
        },
        status_code=200,  # successful authentication
    )
    assert get_cached_access_token() == as_token_model

    # Ensure the cached access token is not retrieved and also removed from the cache
    # if it is invalid
    if invalidity_reason == "invalid":
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/users/me",
            match_headers={
                "Authorization": (
                    f"{Token.model_fields['token_type'].default} {access_token}"
                ),
            },
            status_code=401,  # invalid authentication
        )
    else:  # invalidity_reason == "error"
        httpx_mock.add_exception(
            HTTPError("Internal Server Error"),
            url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/users/me",
            match_headers={
                "Authorization": (
                    f"{Token.model_fields['token_type'].default} {access_token}"
                ),
            },
        )

    assert get_cached_access_token() is None
    assert not cached_access_token_file.exists()

    if invalidity_reason == "error":
        assert "Could not validate cached access token." in caplog.text
