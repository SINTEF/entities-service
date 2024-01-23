"""Test the /_auth endpoint.

The /_auth/token endpoint is tested regularly when retrieving the `client` fixture with
a live backend.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from ...conftest import ClientFixture, GetBackendUserFixture


@pytest.mark.skip_if_not_live_backend(
    reason="Authentication is not supported by mongomock."
)
def test_no_access_user(client: ClientFixture) -> None:
    """Test an error is raised for a user with no login access."""
    from fastapi import status

    with client() as client_:
        response = client_.post(
            "/_auth/token",
            data={
                "grant_type": "password",
                "username": "no_access",
                "password": "test",
            },
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
    assert response.json() == {"detail": "Incorrect username or password"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.skip_if_not_live_backend(
    reason="Authentication is not supported by mongomock."
)
def test_bad_password(
    client: ClientFixture, get_backend_user: GetBackendUserFixture
) -> None:
    """Test an error is raised for a user with no login access."""
    from fastapi import status

    user = get_backend_user("read")
    bad_password = "bad_password"

    assert bad_password != user["password"]

    with client() as client_:
        response = client_.post(
            "/_auth/token",
            data={
                "grant_type": "password",
                "username": user["username"],
                "password": bad_password,
            },
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
    assert response.json() == {"detail": "Incorrect username or password"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
