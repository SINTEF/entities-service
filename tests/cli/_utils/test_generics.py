"""Test the generic CLI utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ...conftest import ParameterizeGetEntities


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


def test_get_namespace_name_version(
    parameterized_entity: ParameterizeGetEntities,
) -> None:
    """Test getting the namespace, name, and version from an entity."""
    from entities_service.cli._utils.generics import get_namespace_name_version
    from entities_service.cli._utils.types import StrReversor
    from entities_service.models import soft_entity

    entity = soft_entity(**parameterized_entity.entity)
    assert not isinstance(entity, list)

    result_from_entity = get_namespace_name_version(entity)
    result_from_dict = get_namespace_name_version(parameterized_entity.entity)

    assert result_from_entity == result_from_dict

    assert isinstance(result_from_entity[-1], StrReversor)
    assert isinstance(result_from_dict[-1], StrReversor)

    # Test failing to parse the URI
    with pytest.raises(ValueError, match="Could not parse URI"):
        get_namespace_name_version({"uri": "invalid-uri"})
