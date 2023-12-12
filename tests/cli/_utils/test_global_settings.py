"""Test edge cases for global settings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typer.testing import CliRunner


def test_multiple_as_file_formats(cli: CliRunner) -> None:
    """Test that multiple values are not allowed for file formats."""
    from random import choice

    from dlite_entities_service.cli.main import APP

    as_file_format_options = ["--json", "--json-one-line", "--yaml"]

    options = [choice(as_file_format_options)]

    # Ensure that the second option is not the same as the first
    while (second_option := choice(as_file_format_options)) in options:
        pass

    options.append(second_option)

    result = cli.invoke(APP, f"{' '.join(options)} upload")
    assert result.exit_code != 0, result.stdout
    assert (
        "Cannot use --json, --yaml/--yml, and --json-one-line together in any "
        "combination." in result.stderr.replace("│\n│ ", "")
    ), result.stdout

    for as_file_format_option in as_file_format_options:
        result = cli.invoke(APP, f"{as_file_format_option} upload")
        assert result.exit_code == 0, result.stderr


def test_version(cli: CliRunner) -> None:
    """Test that the version is printed."""
    from dlite_entities_service import __version__
    from dlite_entities_service.cli.main import APP

    result = cli.invoke(APP, "--version")
    assert result.exit_code == 0, result.stderr
    assert f"dlite-entities-service version: {__version__}" in result.stdout.replace(
        "\n", " "
    ), result.stdout
