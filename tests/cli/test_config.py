"""Tests for `entities-service config` CLI commands."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal

    from typer import Typer
    from typer.testing import CliRunner


def test_config(cli: CliRunner) -> None:
    """Test `entities-service config` CLI command."""
    from dlite_entities_service.cli.config import APP

    result = cli.invoke(APP)
    assert result.exit_code == 0, result.stderr
    assert APP.info.help in result.stdout

    assert result.stdout == cli.invoke(APP, "--help").stdout


@pytest.mark.usefixtures("patch_dotenv_config_paths")
@pytest.mark.parametrize("pass_value", [True, False])
@pytest.mark.parametrize("dotenv_file", ["cli", "service"])
def test_set(
    cli: CliRunner,
    pass_value: bool,
    dotenv_file: Literal["cli", "service"],
    config_app: Typer,
) -> None:
    """Test `entities-service config set` CLI command."""
    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    env_prefix = CONFIG.model_config["env_prefix"]

    for field in ConfigFields:
        if pass_value:
            result = cli.invoke(
                config_app, f"--use-{dotenv_file}-dotenv set {field} {field}_test"
            )
        else:
            result = cli.invoke(
                config_app,
                f"--use-{dotenv_file}-dotenv set {field}",
                input=f"{field}_test",
            )

        assert result.exit_code == 0, result.stderr

        if not pass_value:
            assert f"Enter a value for {field.upper()}:" in result.stdout.replace(
                "\n", ""
            ), result.stderr

        if field.is_sensitive():
            assert (
                f"Set {env_prefix.upper()}{field.upper()} to sensitive value."
                in result.stdout.replace("\n", "")
            ), result.stderr
        else:
            assert (
                f"Set {env_prefix.upper()}{field.upper()} to {field}_test."
                in result.stdout.replace("\n", "")
            ), result.stderr


@pytest.mark.usefixtures("_prefill_dotenv_config")
@pytest.mark.parametrize("dotenv_file", ["cli", "service"])
def test_unset(
    cli: CliRunner,
    dotenv_file: Literal["cli", "service"],
    tmp_path: Path,
    config_app: Typer,
) -> None:
    """Test `entities-service config unset` CLI command."""
    from dotenv import dotenv_values

    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    env_prefix = CONFIG.model_config["env_prefix"]

    dotenv_file_path = tmp_path / f"{CONFIG.model_config['env_file']}_{dotenv_file}"
    assert dotenv_file_path.exists()

    for field in ConfigFields:
        result = cli.invoke(config_app, f"--use-{dotenv_file}-dotenv unset {field}")
        assert result.exit_code == 0, result.stderr
        assert f"Unset {env_prefix.upper()}{field.upper()}." in result.stdout.replace(
            "\n", ""
        ), result.stderr

        assert (
            f"{env_prefix}{field}=".upper() not in dotenv_file_path.read_text()
        ), dotenv_file_path.read_text()
        assert f"{env_prefix}{field}".upper() not in dotenv_values(
            dotenv_file_path
        ), dotenv_values(dotenv_file_path)

    assert dotenv_file_path.read_text() == "", dotenv_file_path.read_text()
    assert dotenv_values(dotenv_file_path) == {}, dotenv_values(dotenv_file_path)

    # Run again to get the "file not found" message
    dotenv_file_path.unlink()
    result = cli.invoke(config_app, f"--use-{dotenv_file}-dotenv unset {field}")
    assert result.exit_code == 0, result.stderr
    assert "file not found." in result.stdout.replace("\n", ""), result.stderr


@pytest.mark.usefixtures("_prefill_dotenv_config")
@pytest.mark.parametrize("dotenv_file", ["cli", "service"])
def test_unset_all(
    cli: CliRunner,
    dotenv_file: Literal["cli", "service"],
    tmp_path: Path,
    config_app: Typer,
) -> None:
    """Test `entities-service config unset-all` CLI command."""
    from dlite_entities_service.service.config import CONFIG

    dotenv_file_path = tmp_path / f"{CONFIG.model_config['env_file']}_{dotenv_file}"
    assert dotenv_file_path.exists()
    assert dotenv_file_path.read_text() != "", dotenv_file_path.read_text()

    result = cli.invoke(config_app, f"--use-{dotenv_file}-dotenv unset-all", input="y")
    assert result.exit_code == 0, result.stderr
    assert "Unset all configuration options." in result.stdout.replace(
        "\n", ""
    ), result.stderr

    assert not dotenv_file_path.exists(), dotenv_file_path

    # Run again to get the "file not found" message
    result = cli.invoke(config_app, f"--use-{dotenv_file}-dotenv unset-all", input="y")
    assert result.exit_code == 0, result.stderr
    assert "file not found." in result.stdout.replace("\n", ""), result.stderr


@pytest.mark.usefixtures("_prefill_dotenv_config")
@pytest.mark.parametrize("dotenv_file", ["cli", "service"])
@pytest.mark.parametrize("reveal_sensitive", [True, False])
def test_show(
    cli: CliRunner,
    config_app: Typer,
    dotenv_file: Literal["cli", "service"],
    reveal_sensitive: bool,
    tmp_path: Path,
) -> None:
    """Test `entities-service config show` CLI command."""
    from dotenv import dotenv_values

    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    dotenv_file_path = tmp_path / f"{CONFIG.model_config['env_file']}_{dotenv_file}"
    assert dotenv_file_path.exists()
    assert dotenv_file_path.read_text() != "", dotenv_file_path.read_text()

    test_dotenv_dict = dotenv_values(dotenv_file_path)

    env_prefix = CONFIG.model_config["env_prefix"]

    reveal_sensitive_cmd = "--reveal-sensitive" if reveal_sensitive else ""

    result = cli.invoke(
        config_app, f"--use-{dotenv_file}-dotenv show {reveal_sensitive_cmd}"
    )
    assert result.exit_code == 0, result.stderr
    assert "Current configuration in" in result.stdout.replace("\n", ""), result.stderr

    for key, value in test_dotenv_dict.items():
        field = ConfigFields(key[len(env_prefix) :].lower())
        resolved_value = (
            "*" * 8 if field.is_sensitive() and not reveal_sensitive else value
        )

        assert f"{key}: {resolved_value}" in result.stdout.replace(
            "\n", ""
        ), f"stdout: {result.stdout}\n\nstderr: {result.stderr}\n\n"


def test_show_file_not_exist(
    cli: CliRunner, config_app: Typer, patch_dotenv_config_paths: Path
) -> None:
    """Test `entities-service config show` CLI command."""
    import re

    for file in patch_dotenv_config_paths.iterdir():
        file.unlink()

    result = cli.invoke(config_app, "show")
    assert result.exit_code == 1, result.stdout
    assert re.match(
        r"No .* file found\.", result.stderr.replace("\n", "")
    ), result.stdout


@pytest.mark.usefixtures("_prefill_dotenv_config")
@pytest.mark.parametrize("reveal_sensitive", [True, False])
def test_show_as_file_format(
    cli: CliRunner, config_app: Typer, tmp_path: Path, reveal_sensitive: bool
) -> None:
    """Test `entities-service config show` CLI command."""
    import json

    import yaml
    from dotenv import dotenv_values

    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    dotenv_file_path = tmp_path / f"{CONFIG.model_config['env_file']}_cli"
    assert dotenv_file_path.exists()
    assert dotenv_file_path.read_text() != "", dotenv_file_path.read_text()

    env_prefix = CONFIG.model_config["env_prefix"]

    test_dotenv_dict = dotenv_values(dotenv_file_path)
    for field in ConfigFields:
        if field.is_sensitive() and not reveal_sensitive:
            key = f"{env_prefix}{field}".upper()
            assert key in test_dotenv_dict
            test_dotenv_dict[key] = "*" * 8

    reveal_sensitive_cmd = "--reveal-sensitive" if reveal_sensitive else ""

    # Test as_json
    result = cli.invoke(
        config_app, f"--use-cli-dotenv --json show {reveal_sensitive_cmd}"
    )
    assert result.exit_code == 0, result.stderr
    assert "Current configuration in" not in result.stdout.replace(
        "\n", ""
    ), result.stdout
    assert json.loads(result.stdout) == test_dotenv_dict, result.stdout
    # There's a new line in several places due to nice indentation in the output
    assert result.stdout.count("\n") > 1, result.stdout

    # Test as_json_one_line
    result = cli.invoke(
        config_app, f"--use-cli-dotenv --json-one-line show {reveal_sensitive_cmd}"
    )
    assert result.exit_code == 0, result.stderr
    assert "Current configuration in" not in result.stdout.replace(
        "\n", ""
    ), result.stdout
    assert json.loads(result.stdout) == test_dotenv_dict, result.stdout
    # There's a final newline at the very end of the output
    assert result.stdout.count("\n") == 1, result.stdout

    # Test as_yaml
    result = cli.invoke(
        config_app, f"--use-cli-dotenv --yaml show {reveal_sensitive_cmd}"
    )
    assert result.exit_code == 0, result.stderr
    assert "Current configuration in" not in result.stdout.replace(
        "\n", ""
    ), result.stdout
    assert yaml.safe_load(result.stdout) == test_dotenv_dict, result.stdout


def test_configfields_autocompletion() -> None:
    """Test the ConfigFields.autocomplete() method."""
    from dlite_entities_service.cli.config import ConfigFields
    from dlite_entities_service.service.config import CONFIG

    test_values = {
        "b": ["base_url"],
        "m": ["mongo_uri", "mongo_user", "mongo_password"],
        "mongo_u": ["mongo_uri", "mongo_user"],
        "mongo_p": ["mongo_password"],
        "mongo_ur": ["mongo_uri"],
        "mongo_us": ["mongo_user"],
    }

    for test_value, expected in test_values.items():
        expected_values = list(
            zip(
                expected,
                [CONFIG.model_fields[_].description for _ in expected],
                strict=True,
            )
        )
        assert (
            list(ConfigFields.autocomplete(test_value)) == expected_values
        ), test_value
