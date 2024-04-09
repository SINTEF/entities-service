"""Test the generic CLI utilities."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("access_token", ["test-token", None])
def test_initialize_access_token(
    access_token: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test initializing the access token."""
    from httpx_auth import HeaderApiKey
    from pydantic import SecretStr

    from entities_service.service.config import ServiceSettings

    if access_token is not None:
        monkeypatch.setattr(
            "entities_service.cli._utils.generics.CONFIG",
            ServiceSettings(access_token=SecretStr(access_token)),
        )

    from entities_service.cli._utils.generics import initialize_access_token

    oauth = initialize_access_token()
    if access_token is None:
        assert oauth is None
    else:
        assert isinstance(oauth, HeaderApiKey)
        assert oauth.api_key == f"Bearer {access_token}"
