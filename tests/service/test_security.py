"""Test the entities_service.service.security module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Any, Literal

    from pytest_httpx import HTTPXMock

    from ..conftest import MockOpenIDConfigCall


@pytest.fixture()
def user_info() -> dict[str, Any]:
    """Test data for verify_user_access_token() function."""
    return {
        "id": 1,
        "username": "john_smith",
        "name": "John Smith",
        "state": "active",
        "locked": False,
        "avatar_url": "http://localhost:3000/uploads/user/avatar/1/cd8.jpeg",
        "web_url": "http://localhost:3000/john_smith",
        "created_at": "2012-05-23T08:00:58Z",
        "bio": "",
        "bot": False,
        "location": None,
        "public_email": "john@example.com",
        "skype": "",
        "linkedin": "",
        "twitter": "",
        "discord": "",
        "website_url": "",
        "organization": "",
        "job_title": "Operations Specialist",
        "pronouns": "he/him",
        "work_information": None,
        "followers": 1,
        "following": 1,
        "local_time": "3:38 PM",
        "is_followed": False,
    }


@pytest.fixture()
def group_member_info() -> dict[str, Any]:
    """Test data for verify_user_access_token() function."""
    return {
        "id": 1,
        "username": "john_smith",
        "name": "John Smith",
        "state": "active",
        "avatar_url": "http://localhost:3000/uploads/user/avatar/1/cd8.jpeg",
        "web_url": "http://localhost:3000/john_smith",
        "access_level": 30,  # Developer
        "email": "john@example.com",
        "created_at": "2012-10-22T14:13:35Z",
        "created_by": {
            "id": 2,
            "username": "john_doe",
            "name": "John Doe",
            "state": "active",
            "avatar_url": "https://www.gravatar.com/avatar/c2525a7f58ae3776070e44c106c48e15?s=80&d=identicon",
            "web_url": "http://192.168.1.8:3000/root",
        },
        "expires_at": None,
        "group_saml_identity": None,
    }


async def test_get_openid_config(mock_openid_config_call: MockOpenIDConfigCall) -> None:
    """Test get_openid_config() function."""
    from entities_service.models.auth import OpenIDConfiguration
    from entities_service.service.config import CONFIG
    from entities_service.service.security import get_openid_config

    # Mock successful OpenID configuration response
    mock_openid_config_call(str(CONFIG.oauth2_provider_base_url).rstrip("/"))

    assert isinstance(await get_openid_config(), OpenIDConfiguration)


async def test_openid_source_down(httpx_mock: HTTPXMock) -> None:
    """Test get_openid_config() function raises ValueError when the OpenID source is
    down.

    The HTTPX standard protocol is to raise a TimeoutException when the server is
    unreachable.
    """
    from httpx import TimeoutException

    from entities_service.service.security import get_openid_config

    # Mock HTTP Timeout
    httpx_mock.add_exception(TimeoutException("Connection timeout."))

    with pytest.raises(ValueError, match="Could not get OpenID configuration."):
        await get_openid_config()


async def test_openid_config_parse_error(httpx_mock: HTTPXMock) -> None:
    """Test get_openid_config() function raises ValueError when the OpenID
    configuration cannot be parsed."""
    from pydantic import ValidationError

    from entities_service.models.auth import OpenIDConfiguration
    from entities_service.service.security import get_openid_config

    invalid_openid_response = {"invalid": "response"}

    # Ensure invalid OpenID configuration response is invalid
    with pytest.raises(ValidationError):
        OpenIDConfiguration(**invalid_openid_response)

    # Mock invalid OpenID configuration response
    httpx_mock.add_response(json=invalid_openid_response)

    with pytest.raises(ValueError, match="Could not parse OpenID configuration."):
        await get_openid_config()


async def test_verify_user_access_token(
    httpx_mock: HTTPXMock,
    user_info: dict[str, Any],
    group_member_info: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test verify_user_access_token() function.

    "Test data" is lifted from the GitLab documentation.
    """
    from urllib.parse import quote_plus

    from entities_service.models.auth import (
        GitLabGroupProjectMember,
        GitLabRole,
        GitLabUser,
    )
    from entities_service.service.config import CONFIG
    from entities_service.service.security import verify_user_access_token

    mock_token = "mock_token"

    # Validate test data will result in successful "passage" through the function
    parsed_user = GitLabUser(**user_info)
    assert parsed_user.state == "active"
    assert parsed_user.locked is False

    parsed_member = GitLabGroupProjectMember(**group_member_info)
    for attr in ("id", "username", "name", "state"):
        assert getattr(parsed_member, attr) == getattr(parsed_user, attr)
    assert parsed_member.access_level >= GitLabRole.DEVELOPER  # Minimum access level

    # Mock successful responses
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )
    httpx_mock.add_response(
        url=(
            f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/groups/"
            f"{quote_plus(CONFIG.roles_group)}/members/{user_info['id']}"
        ),
        json=group_member_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token(mock_token) == (True, None, None)

    assert (
        f"User {parsed_member.name} ({parsed_member.id}, {parsed_member.username}) has "
        "the rights to create entities."
    ) in caplog.messages
    assert f"User: {parsed_user.name}" in caplog.messages


@pytest.mark.parametrize("user_state", ["blocked", "locked"])
async def test_verify_user_access_token_inactive_user(
    httpx_mock: HTTPXMock,
    user_info: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    user_state: Literal["blocked", "locked"],
) -> None:
    """Test verify_user_access_token() function returns False with a blocked or locked
    (inactive) user."""
    from entities_service.models.auth import GitLabUser
    from entities_service.service.config import CONFIG
    from entities_service.service.security import verify_user_access_token

    mock_token = "mock_token"

    # Set user state to blocked or locked
    if user_state == "blocked":
        user_info["state"] = "blocked"
    else:
        user_info["state"] = "active"
        user_info["locked"] = True

    # Validate test data is still valid according to the model
    assert GitLabUser(**user_info)

    # Mock successful response
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token(mock_token) == (
            False,
            403,
            "Your user account is not active or is locked. "
            "Please contact your GitLab administrator(s).",
        )

    assert (
        f"User is not active or is locked. (Username: {user_info['username']})"
        in caplog.messages
    )


@pytest.mark.parametrize(
    ("differing_attr", "differing_value"),
    [
        ("id", 2),
        ("username", "raymond_smith"),
        ("name", "Raymond Smith"),
        ("state", "blocked"),
    ],
)
async def test_verify_user_access_token_different_member(
    httpx_mock: HTTPXMock,
    user_info: dict[str, Any],
    group_member_info: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    differing_attr: Literal["id", "username", "name", "state"],
    differing_value: Literal[2, "raymond_smith", "Raymond Smith", "blocked"],
) -> None:
    """Test verify_user_access_token() function returns False if a returned group member
    differs from the current user."""
    from urllib.parse import quote_plus

    from entities_service.models.auth import GitLabGroupProjectMember, GitLabUser
    from entities_service.service.config import CONFIG
    from entities_service.service.security import verify_user_access_token

    mock_token = "mock_token"

    # Validate test data is still valid according to the model
    assert GitLabUser(**user_info)

    # Set group member info to differ from user info
    group_member_info[differing_attr] = differing_value
    assert group_member_info[differing_attr] != user_info[differing_attr]
    assert GitLabGroupProjectMember(**group_member_info)

    # Mock successful responses
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )
    httpx_mock.add_response(
        url=(
            f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/groups/"
            f"{quote_plus(CONFIG.roles_group)}/members/{user_info['id']}"
        ),
        json=group_member_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token(mock_token) == (False, None, None)

    assert "Member info does not match the user info." in caplog.messages


async def test_verify_user_access_token_bad_access_level(
    httpx_mock: HTTPXMock,
    user_info: dict[str, Any],
    group_member_info: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test verify_user_access_token() function returns False if a user has an access
    level below the minimum required (DEVELOPER)."""
    from urllib.parse import quote_plus

    from entities_service.models.auth import (
        GitLabGroupProjectMember,
        GitLabRole,
        GitLabUser,
    )
    from entities_service.service.config import CONFIG
    from entities_service.service.security import (
        MINIMUM_GROUP_ACCESS_LEVEL,
        verify_user_access_token,
    )

    mock_token = "mock_token"

    # Validate test data is still valid according to the model
    assert GitLabUser(**user_info)

    # Set group member access level to below the minimum required
    assert GitLabRole.NO_ACCESS < MINIMUM_GROUP_ACCESS_LEVEL
    group_member_info["access_level"] = GitLabRole.NO_ACCESS
    parsed_member = GitLabGroupProjectMember(**group_member_info)

    # Mock successful responses
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )
    httpx_mock.add_response(
        url=(
            f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/groups/"
            f"{quote_plus(CONFIG.roles_group)}/members/{user_info['id']}"
        ),
        json=group_member_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token(mock_token) == (
            False,
            403,
            (
                "You do not have the rights to create entities. "
                "Please contact the entities-service group maintainer."
            ),
        )

    assert (
        "User does not have the rights to create entities. Hint: Change "
        f"{parsed_member.username}'s role in the GitLab group {CONFIG.roles_group!r}"
    ) in caplog.messages


async def test_verify_user_access_token_source_down(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test verify_user_access_token() function returns False when the OAuth2 source is
    down."""
    from httpx import TimeoutException

    from entities_service.service.security import verify_user_access_token

    # Mock HTTP Timeout
    httpx_mock.add_exception(TimeoutException("Connection timeout."))

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token("mock_token") == (False, None, None)

    assert "Connection timeout." in caplog.text
    assert "Could not get user info from GitLab provider." in caplog.messages


async def test_verify_user_access_token_source_down_midway(
    httpx_mock: HTTPXMock, user_info: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Test verify_user_access_token() function returns False when the OAuth2 source
    goes down in between calls."""
    from urllib.parse import quote_plus

    from httpx import TimeoutException

    from entities_service.models.auth import GitLabUser
    from entities_service.service.config import CONFIG
    from entities_service.service.security import verify_user_access_token

    mock_token = "mock_token"

    # Validate test data is still valid according to the model
    assert GitLabUser(**user_info)

    # Mock successful initial response
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )

    # Mock HTTP Timeout
    httpx_mock.add_exception(
        TimeoutException("Connection timeout."),
        url=(
            f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/groups/"
            f"{quote_plus(CONFIG.roles_group)}/members/{user_info['id']}"
        ),
    )

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token("mock_token") == (
            False,
            403,
            (
                "You are not a member of the entities-service group. "
                "Please contact the entities-service group maintainer."
            ),
        )

    assert "Connection timeout." in caplog.text
    assert "User is not a member of the entities-service group." in caplog.messages


async def test_verify_user_access_token_user_is_not_member(
    httpx_mock: HTTPXMock,
    user_info: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test verify_user_access_token() function returns False when a user is not a
    member of the entities-service group."""
    from urllib.parse import quote_plus

    from entities_service.models.auth import GitLabUser
    from entities_service.service.config import CONFIG
    from entities_service.service.security import verify_user_access_token

    mock_token = "mock_token"

    # Validate test data is still valid according to the model
    assert GitLabUser(**user_info)

    # Mock successful responses
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )
    httpx_mock.add_response(
        url=(
            f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/groups/"
            f"{quote_plus(CONFIG.roles_group)}/members/{user_info['id']}"
        ),
        json={"error": "404 Not Found"},
        status_code=404,
    )

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token(mock_token) == (
            False,
            403,
            (
                "You are not a member of the entities-service group. "
                "Please contact the entities-service group maintainer."
            ),
        )

    assert "Connection timeout." not in caplog.text
    assert "User is not a member of the entities-service group." in caplog.messages


async def test_verify_user_access_token_parse_error_user(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test verify_user_access_token() function returns False when the user info cannot
    be parsed."""
    import json

    from entities_service.service.security import verify_user_access_token

    # Mock invalid user info response
    httpx_mock.add_response(json={"invalid": "response"})

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token("mock_token") == (False, None, None)

    assert "Could not parse user info from GitLab provider." in caplog.messages
    assert f"Response:\n{json.dumps({'invalid': 'response'})}" in caplog.messages


async def test_verify_user_access_token_parse_error_member(
    httpx_mock: HTTPXMock,
    user_info: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test verify_user_access_token() function returns False when the group member info
    cannot be parsed."""
    import json

    from entities_service.models.auth import GitLabUser
    from entities_service.service.config import CONFIG
    from entities_service.service.security import verify_user_access_token

    mock_token = "mock_token"

    # Validate test data is still valid according to the model
    assert GitLabUser(**user_info)

    # Mock successful initial response
    httpx_mock.add_response(
        url=f"{str(CONFIG.oauth2_provider_base_url).rstrip('/')}/api/v4/user",
        json=user_info,
        headers={"Authorization": f"Bearer {mock_token}"},
    )

    # Mock invalid group member info response
    httpx_mock.add_response(json={"invalid": "response"})

    with caplog.at_level("DEBUG", logger="entities_service"):
        assert await verify_user_access_token(mock_token) == (False, None, None)

    assert "Could not parse user info from GitLab provider." not in caplog.messages
    assert "Could not parse member role from GitLab provider." in caplog.messages
    assert f"Response:\n{json.dumps({'invalid': 'response'})}" in caplog.messages
