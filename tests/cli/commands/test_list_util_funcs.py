"""Tests for `entities-service list` CLI command's utility functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from typing import Literal

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


def test_parse_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the _parse_namespace function."""
    # Patch CONFIG.base_url
    from pydantic import AnyHttpUrl

    core_namespace = "http://example.com"

    monkeypatch.setattr(
        "entities_service.cli.commands.list.CONFIG.base_url", AnyHttpUrl(core_namespace)
    )

    # Perform tests
    from entities_service.cli.commands.list import _parse_namespace

    # Test with a valid namespace
    parsed_namespace = _parse_namespace(core_namespace)
    assert parsed_namespace == core_namespace

    # Test with a valid namespace with trailing slash
    parsed_namespace = _parse_namespace(core_namespace + "/")
    assert parsed_namespace == core_namespace

    # Test with a non-core namespace
    external_namespace = "http://example.org"
    assert not external_namespace.startswith(core_namespace)
    parsed_namespace = _parse_namespace(external_namespace)
    assert parsed_namespace == external_namespace

    # Test with a non-core specific namespace
    external_namespace = "http://example.org/test/"
    assert not external_namespace.startswith(core_namespace)
    parsed_namespace = _parse_namespace(external_namespace)
    assert parsed_namespace == external_namespace.rstrip("/")

    # Test with a non-URL namespace
    specific_namespace = "test"
    parsed_namespace = _parse_namespace(specific_namespace)
    assert parsed_namespace == f"{core_namespace}/{specific_namespace}"

    # Test with a fully qualified specific namespace URL
    specific_namespace = f"{core_namespace}/test/"
    parsed_namespace = _parse_namespace(specific_namespace)
    assert parsed_namespace == specific_namespace.rstrip("/")

    # Test with a uri as URL
    uri = f"{core_namespace}/test/1.0/Test"
    parsed_namespace = _parse_namespace(uri)
    assert parsed_namespace == f"{core_namespace}/test"

    # Test core namespace is returned for None, "/", and an empty string
    for namespace in (None, "/", ""):
        parsed_namespace = _parse_namespace(namespace)
        assert parsed_namespace == core_namespace


@pytest.mark.parametrize("allow_external", [True, False])
def test_parse_namespace_valueerror(
    monkeypatch: pytest.MonkeyPatch, allow_external: Literal[True, False]
) -> None:
    """Test the _parse_namespace raises a ValueError according to `allow_external`
    parameter."""
    # Patch CONFIG.base_url
    from pydantic import AnyHttpUrl

    core_namespace = "http://example.com"

    monkeypatch.setattr(
        "entities_service.cli.commands.list.CONFIG.base_url", AnyHttpUrl(core_namespace)
    )

    # Perform tests
    import re

    from entities_service.cli.commands.list import _parse_namespace

    non_core_namespace = "http://example.org/test/"
    assert not non_core_namespace.startswith(core_namespace)

    if allow_external:
        # Test with a non-core namespace
        parsed_namespace = _parse_namespace(
            non_core_namespace, allow_external=allow_external
        )
        assert parsed_namespace == non_core_namespace.rstrip("/")
    else:
        with pytest.raises(
            ValueError,
            match=(
                rf"^{re.escape(non_core_namespace)} is not within the core namespace "
                rf"{re.escape(core_namespace)} and external namespaces are not allowed "
                r"\(set 'allow_external=True'\)\.$"
            ),
        ):
            _parse_namespace(non_core_namespace, allow_external=allow_external)


def test_get_specific_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the _get_specific_namespace function."""
    # Patch CONFIG.base_url
    from pydantic import AnyHttpUrl

    core_namespace = "http://example.com"

    monkeypatch.setattr(
        "entities_service.cli.commands.list.CONFIG.base_url", AnyHttpUrl(core_namespace)
    )

    # Perform tests
    from entities_service.cli.commands.list import _get_specific_namespace

    specific_namespace = "test"

    # Test with a fully qualified URL
    namespace = f"{core_namespace}/{specific_namespace}"
    parsed_specific_namespace = _get_specific_namespace(namespace)
    assert parsed_specific_namespace == specific_namespace

    # Test with a fully qualified URL with trailing slash
    namespace = f"{core_namespace}/{specific_namespace}/"
    parsed_specific_namespace = _get_specific_namespace(namespace)
    assert parsed_specific_namespace == specific_namespace

    # Test with a specific namespace
    parsed_specific_namespace = _get_specific_namespace(specific_namespace)
    assert parsed_specific_namespace == specific_namespace

    # Test with a specific namespace with trailing slash
    parsed_specific_namespace = _get_specific_namespace(f"{specific_namespace}/")
    assert parsed_specific_namespace == specific_namespace

    # Test with " ", "/", and an empty string
    for namespace in (" ", "/", ""):
        parsed_namespace = _get_specific_namespace(namespace)
        assert parsed_namespace is None


def test_get_specific_namespace_expectations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the expectations mentioned in the doc-string of _get_specific_namespace
    holds true.

    Mainly this is here to test that if error-handling is ever introduced to this
    function, this test will fail making the developer aware of the change.
    """
    # Patch CONFIG.base_url
    from pydantic import AnyHttpUrl

    core_namespace = "http://example.com"

    monkeypatch.setattr(
        "entities_service.cli.commands.list.CONFIG.base_url", AnyHttpUrl(core_namespace)
    )

    # Perform tests
    from entities_service.cli.commands.list import _get_specific_namespace

    # Test with an external namespace
    # This is not supported, but also not checked.
    # The external namespace should be returned as is (with any trailing or prepended
    # slashes removed).
    external_namespace = "http://example.org"
    assert not external_namespace.startswith(core_namespace)

    namespace = f"{external_namespace}/test/"
    parsed_specific_namespace = _get_specific_namespace(namespace)
    assert parsed_specific_namespace == namespace.rstrip("/")

    # Test passing `None` as the namespace
    # This is not tested by the function, but is allowed by `_parse_namespace()`, so
    # one might be confusied thinking it should also be allowed here, but that is not
    # the case.
    # Again, this is not checked due to the use case of the `_get_specific_namespace()`
    # function.
    with pytest.raises(AttributeError):
        # As the first thing in the function is `namespace.startswith(...)` an
        # AttributeError should be raised if `namespace` is `None`.
        _get_specific_namespace(None)
