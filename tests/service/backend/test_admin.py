"""Test the Admin backend."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from dlite_entities_service.service.backend.admin import AdminBackend

    from ...conftest import GetBackendUserFixture


@pytest.fixture()
def admin_backend(live_backend: bool) -> AdminBackend:
    """Get an admin backend."""
    from dlite_entities_service.service.backend.admin import AdminBackend
    from dlite_entities_service.service.config import CONFIG

    backend_settings = {}
    if live_backend:
        backend_settings.update(
            {
                "mongo_username": (
                    CONFIG.admin_user.get_secret_value()
                    if CONFIG.admin_user is not None
                    else "root"
                ),
                "mongo_password": (
                    CONFIG.admin_password.get_secret_value()
                    if CONFIG.admin_password is not None
                    else "root"
                ),
            }
        )

    return AdminBackend(settings=backend_settings)


def test_unused_must_implement_methods(admin_backend: AdminBackend) -> None:
    """Test all the abstract must-implement Backend classes raises
    NotImplementedError."""
    methods = {
        "initialize": (),
        "create": (None,),
        "read": (None,),
        "update": (None, None),
        "delete": (None,),
        "search": (None,),
        "count": (None,),
    }

    # Also test __contains__, __iter__, and __len__
    with pytest.raises(NotImplementedError):
        # __contains__
        assert "test_user" in admin_backend

    with pytest.raises(NotImplementedError):
        # __iter__
        next(iter(admin_backend))

    with pytest.raises(NotImplementedError):
        # __len__
        len(admin_backend)

    for method, args in methods.items():
        with pytest.raises(NotImplementedError):
            getattr(admin_backend, method)(*args)


def test_close(live_backend: bool) -> None:
    """Test closing the backend."""
    from dlite_entities_service.service.backend.admin import AdminBackend
    from dlite_entities_service.service.backend.mongodb import MONGO_CLIENTS

    original_number_of_clients = 2 if live_backend else 1

    assert MONGO_CLIENTS is not None
    assert len(MONGO_CLIENTS) == original_number_of_clients

    backend = AdminBackend(
        settings={
            "mongo_username": "test_root",
            "mongo_password": "test_password",
        },
    )

    assert len(MONGO_CLIENTS) == original_number_of_clients + 1
    assert (hash("test_root"), hash("test_roottest_password")) in MONGO_CLIENTS

    backend.close()

    if live_backend:
        # The client should successfully have been closed and removed from the cache
        assert len(MONGO_CLIENTS) == original_number_of_clients
        assert (hash("test_root"), hash("test_roottest_password")) not in MONGO_CLIENTS
    else:
        # The client should not have been closed or removed from the cache
        assert len(MONGO_CLIENTS) == original_number_of_clients + 1
        assert (hash("test_root"), hash("test_roottest_password")) in MONGO_CLIENTS

        # Remove the client from the cache
        del MONGO_CLIENTS[(hash("test_root"), hash("test_roottest_password"))]
        assert len(MONGO_CLIENTS) == original_number_of_clients


@pytest.mark.skip_if_not_live_backend(reason="Admin backend is not used for mongomock.")
def test_get_user(
    admin_backend: AdminBackend, get_backend_user: GetBackendUserFixture
) -> None:
    """Test getting a user."""
    non_existant_user = "test_user"
    read_user = get_backend_user("read")
    write_user = get_backend_user("readWrite")

    assert non_existant_user not in [read_user["username"], write_user["username"]]

    # Password is not part of the returned user from get_user()
    read_user.pop("password")
    write_user.pop("password")

    assert admin_backend.get_user(non_existant_user) is None
    assert admin_backend.get_user(read_user["username"]) == read_user
    assert admin_backend.get_user(write_user["username"]) == write_user


@pytest.mark.skip_if_not_live_backend(reason="Admin backend is not used for mongomock.")
def test_get_users(
    admin_backend: AdminBackend, get_backend_user: GetBackendUserFixture
) -> None:
    """Test getting all users."""
    read_user = get_backend_user("read")
    write_user = get_backend_user("readWrite")
    admin_user = {
        "username": admin_backend._settings.mongo_username.get_secret_value(),
        "full_name": None,
        "roles": [{"db": "admin", "role": "root"}],
    }
    list_of_users = [read_user, write_user, admin_user]

    # Password is not part of the returned user from get_user()
    read_user.pop("password")
    write_user.pop("password")

    for user in admin_backend.get_users():
        assert user in list_of_users

    assert len(list(admin_backend.get_users())) == len(list_of_users)
