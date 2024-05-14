"""Unit tests for the `cli._utils.types` module."""

from __future__ import annotations


def test_StrReversor() -> None:
    """Test the `StrReversor` class reverts sorting order."""
    from entities_service.cli._utils.types import StrReversor

    test_list = [("a", 1), ("b", 1), ("a", 2), ("b", 2)]
    ascending_str_descending_int_list = [("a", 2), ("a", 1), ("b", 2), ("b", 1)]

    # Sort by the first element in ascending order and the second element in descending
    # order using StrReversor
    test_list.sort(key=lambda x: (x[0], StrReversor(x[1])))
    assert test_list == ascending_str_descending_int_list

    # Test StrReversor comparison against non-StrReversor objects
    assert StrReversor("a") == "a"
    assert "a" == StrReversor("a")  # noqa: SIM300

    # Reversed comparison due to StrReversor
    assert StrReversor("b") < "a"

    # Normal comparison, since StrReversor is on the right and `str.__lt__` is called
    assert "a" < StrReversor("b")  # noqa: SIM300
