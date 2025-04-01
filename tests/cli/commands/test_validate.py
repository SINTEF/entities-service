"""Tests for `entities-service validate` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

    from pytest_httpx import HTTPXMock
    from typer.testing import CliRunner

    from ...conftest import ParameterizeGetEntities

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


def test_validate_no_args(cli: CliRunner) -> None:
    """Test `entities-service validate` with no arguments."""
    from entities_service.cli.commands.validate import validate
    from entities_service.cli.main import APP

    result = cli.invoke(APP, "validate")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert validate.__doc__ in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert result.stdout == cli.invoke(APP, "validate --help").stdout


@pytest.mark.parametrize("quiet", [True, False])
def test_validate_filepath(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    namespace: str | None,
    tmp_path: Path,
    quiet: bool,
) -> None:
    """Test validate with a filepath."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace

    assert "uri" in raw_entity

    if namespace:
        # Update the entity's namespace to the current namespace
        if "namespace" in raw_entity:
            raw_entity["namespace"] = current_namespace

        raw_entity["uri"] = raw_entity["uri"].replace(
            f"{core_namespace}/", f"{current_namespace}/"
        )

        # Write the updated entity to file
        entity_filepath = tmp_path / "Person.json"
        entity_filepath.write_text(json.dumps(raw_entity))

    # Mock response for "Check if entity already exists"
    httpx_mock.add_response(
        url=raw_entity["uri"],
        status_code=404,  # not found
    )

    result = cli.invoke(APP, f"validate {'--quiet ' if quiet else ''}{entity_filepath}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    if quiet:
        assert "Valid Entities" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
    else:
        assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )


@pytest.mark.parametrize("quiet", [True, False])
@pytest.mark.parametrize("fail_fast", [True, False])
def test_validate_filepath_invalid(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    namespace: str | None,
    tmp_path: Path,
    quiet: bool,
) -> None:
    """Test validate with an invalid filepath."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace

    invalid_entity_filepath = static_dir / "invalid_entities" / "Person.json"

    if namespace:
        # Update invalid entity to the current namespace
        # This is to ensure the same error is given when hitting the specific namespace
        # endpoint
        invalid_entity: dict[str, Any] = json.loads(invalid_entity_filepath.read_text())

        assert "identity" not in invalid_entity

        if "namespace" in invalid_entity:
            invalid_entity["namespace"] = current_namespace
        if "uri" in invalid_entity:
            invalid_entity["uri"] = invalid_entity["uri"].replace(
                f"{core_namespace}/", f"{current_namespace}/"
            )
        # Write the updated entity to file
        invalid_entity_filepath = tmp_path / "Person.json"
        invalid_entity_filepath.write_text(json.dumps(invalid_entity))

    result = cli.invoke(
        APP,
        f"validate {'--quiet ' if quiet else ''}{'--fail-fast ' if fail_fast else ''}"
        f"{invalid_entity_filepath}",
    )

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Person.json contains an invalid SOFT entity:" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "validation error for DLiteSOFT7Entity" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "validation errors for DLiteSOFT5Entity" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    failure_summary_text = (
        "Failed to validate one or more entities. See above for more details."
    )

    if fail_fast:
        assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
        assert (
            failure_summary_text not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert failure_summary_text in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        if quiet:
            assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )
        else:
            assert (
                result.stdout.replace("\n", "")
                == "There were no valid entities among the supplied sources."
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )


def test_validate_filepath_invalid_format(cli: CliRunner, tmp_path: Path) -> None:
    """Test validate with an invalid file format."""
    from entities_service.cli.main import APP

    (tmp_path / "Person.txt").touch()

    result = cli.invoke(APP, f"validate {tmp_path / 'Person.txt'}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert result.stderr.count("File format 'txt' is not supported.") == 1
    assert "Skipping file:" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "There were no valid entities among the supplied sources." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


def test_validate_no_source_or_file_or_dir(cli: CliRunner) -> None:
    """Test error when no SOURCE, file or directory are provided (the latter two are
    deprecated)."""
    from entities_service.cli.main import APP

    result = cli.invoke(APP, "validate --format json")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Error: Please, provide at least one SOURCE" in result.stderr
    assert not result.stdout


def test_validate_non_existent_file(cli: CliRunner, tmp_path: Path) -> None:
    """Test error when a non-existent file is provided."""
    from entities_service.cli.main import APP

    non_existent_path = tmp_path / "non_existant.json"

    result = cli.invoke(APP, f"validate {non_existent_path}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert f"Error: Path '{non_existent_path}' does not exist." in result.stderr
    assert not result.stdout


def test_validate_directory(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test validate with a directory."""
    import json

    from entities_service.cli import main
    from entities_service.service.config import CONFIG

    directory = static_dir / "valid_entities"
    raw_entities: list[dict[str, Any]] = [
        json.loads(filepath.read_bytes()) for filepath in directory.glob("*.json")
    ]

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace

    if namespace:
        directory = tmp_path / "valid_entities"
        directory.mkdir(parents=True, exist_ok=True)
        for index, raw_entity in enumerate(raw_entities):
            # Update the entity's namespace to the current namespace
            id_key = "identity" if "identity" in raw_entity else "uri"

            if "namespace" in raw_entity:
                raw_entity["namespace"] = current_namespace
            if id_key in raw_entity:
                raw_entity[id_key] = raw_entity[id_key].replace(
                    f"{core_namespace}/", f"{current_namespace}/"
                )

            # Write the updated entity to file
            (directory / f"{index}.json").write_text(json.dumps(raw_entity))

    # Mock response for "Check if entity already exists"
    for raw_entity in raw_entities:
        id_key = "identity" if "identity" in raw_entity else "uri"
        assert id_key in raw_entity
        httpx_mock.add_response(
            url=raw_entity[id_key],
            status_code=404,  # not found
        )

    result = cli.invoke(main.APP, f"validate {directory}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


def test_validate_empty_dir(cli: CliRunner, tmp_path: Path) -> None:
    """Test validate with no valid files found.

    The outcome here should be the same whether an empty directory is
    provided or a directory with only invalid files.
    """
    from entities_service.cli import main

    empty_dir = tmp_path / "empty_dir"
    assert not empty_dir.exists()
    empty_dir.mkdir()

    yaml_dir = tmp_path / "yaml_dir"
    assert not yaml_dir.exists()
    yaml_dir.mkdir()
    (yaml_dir / "Person.yaml").touch()

    for directory in (empty_dir, yaml_dir):
        result = cli.invoke(main.APP, f"validate --format json {directory}")

        assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
        assert (
            "Error: No files found with the given options." in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        assert not result.stdout


def test_validate_files_with_unchosen_format(cli: CliRunner, static_dir: Path) -> None:
    """Test validating several files with a non-chosen format."""
    from entities_service.cli.main import APP

    directory = static_dir / "valid_entities"
    file_inputs = " ".join(str(filepath) for filepath in directory.glob("*.json"))

    result = cli.invoke(APP, f"validate --format yaml {file_inputs}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "There were no valid entities among the supplied sources." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert all(
        f"Skipping file: ./{filepath.relative_to(static_dir.parent.parent.resolve())}"
        in result.stdout.replace("\n", "")
        for filepath in directory.glob("*.json")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        result.stdout.replace("\n", " ").count(
            "Entities using the file format 'json' can be handled by adding the "
            "option: --format=json"
        )
        == 1
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.parametrize("fail_fast", [True, False])
def test_validate_directory_invalid_entities(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test validating a directory full of invalid entities.

    This test ensures all invalid entities are recognized and reported prior to any
    attempts to validate.
    """
    import json
    import re

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    directory = static_dir / "invalid_entities"

    if namespace:
        core_namespace = str(CONFIG.base_url).rstrip("/")
        current_namespace = f"{core_namespace}/{namespace}"

        directory = tmp_path / "invalid_entities"
        directory.mkdir(parents=True, exist_ok=True)
        for filepath in static_dir.glob("invalid_entities/*.json"):
            # Update invalid entity to the current namespace
            # This is to ensure the same error is given when hitting the specific
            # namespace endpoint
            invalid_entity: dict[str, Any] = json.loads(filepath.read_text())

            id_key = "identity" if "identity" in invalid_entity else "uri"

            if "namespace" in invalid_entity:
                invalid_entity["namespace"] = invalid_entity["namespace"].replace(
                    core_namespace, current_namespace
                )
            if id_key in invalid_entity:
                invalid_entity[id_key] = invalid_entity[id_key].replace(
                    f"{core_namespace}/", f"{current_namespace}/"
                )

            # Write the updated entity to file
            (directory / filepath.name).write_text(json.dumps(invalid_entity))

    result = cli.invoke(
        APP, f"validate {'--fail-fast ' if fail_fast else ''}{directory}"
    )

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        re.search(r"validation errors? for DLiteSOFT7Entity", result.stderr) is not None
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        re.search(r"validation errors? for DLiteSOFT5Entity", result.stderr) is not None
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    failure_summary_text = (
        "Failed to validate one or more entities. See above for more details."
    )

    if fail_fast:
        assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        errored_entity = set()
        for invalid_entity in directory.glob("*.json"):
            if (
                f"{invalid_entity.name} contains an invalid SOFT entity:"
                in result.stderr
            ):
                errored_entity.add(invalid_entity.name)
        assert len(errored_entity) == 1

        assert (
            failure_summary_text not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert (
            result.stdout.replace("\n", "")
            == "There were no valid entities among the supplied sources."
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        assert all(
            f"{invalid_entity.name} contains an invalid SOFT entity:" in result.stderr
            for invalid_entity in directory.glob("*.json")
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        assert failure_summary_text in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )


@pytest.mark.parametrize("no_external_calls", [True, False])
@pytest.mark.parametrize("call_type", ["func", "cli"])
def test_existing_entity(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
    call_type: Literal["func", "cli"],
    no_external_calls: bool,
) -> None:
    """Test that the correct conclusion is drawn; that an external entity already exists

    When called as a function, ensure this result is returned as expected (when using
    `return_full_info=True`).
    When called as a CLI command, ensure the same result is presented in the output.
    """
    import json

    if call_type == "func":
        from entities_service.cli._utils.types import ValidEntity
        from entities_service.cli.commands.validate import validate
    else:
        from entities_service.cli.main import APP

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

    if not no_external_calls:
        # Mock response for "Check if entity already exists"
        assert "uri" in raw_entity
        httpx_mock.add_response(
            url=raw_entity["uri"],
            status_code=200,  # ok
            json=raw_entity,
        )

    if call_type == "func":
        valid_entity = validate(
            filepaths=[entity_filepath],
            return_full_info=True,
            no_external_calls=no_external_calls,
        )

        assert isinstance(valid_entity, list)
        assert all(isinstance(entity, ValidEntity) for entity in valid_entity)

        assert len(valid_entity) == 1
        assert (
            valid_entity[0].entity.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            == raw_entity
        )

        if no_external_calls:
            assert valid_entity[0].exists_remotely is None
            assert valid_entity[0].equal_to_remote is None
            assert valid_entity[0].pretty_diff is None
        else:
            assert valid_entity[0].exists_remotely is True
            assert valid_entity[0].equal_to_remote is True
            assert valid_entity[0].pretty_diff is None

        captured = capsys.readouterr()

        stdout, stderr = captured.out, captured.err
    else:
        result = cli.invoke(
            APP,
            f"validate {'--no-external-calls ' if no_external_calls else ''}"
            f"{entity_filepath}",
        )

        assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        if no_external_calls:
            # The first 'Unknown' explains that it is unknown whether the entity exists
            # externally.
            # The second 'Unknown' explains that it is unknown whether a possible
            # external entity is equal to the local entity.
            assert "/Person0.1UnknownUnknown" in result.stdout.replace(
                " ", ""
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )
        else:
            # The first 'Yes' explains that the entity already exists externally.
            # The second 'Yes' explains that the entity is equal to the remote entity.
            assert "/Person0.1YesYes" in result.stdout.replace(
                " ", ""
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )

        stdout, stderr = result.stdout, result.stderr

    # Common assertions
    assert (
        "There were no valid entities among the supplied sources." not in stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)
    assert not stderr, CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)

    if no_external_calls:
        assert (
            "No external calls will be made" in stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)
    else:
        assert (
            "No external calls will be made" not in stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)


@pytest.mark.parametrize("no_external_calls", [True, False])
@pytest.mark.parametrize("verbose", [True, False])
@pytest.mark.parametrize("call_type", ["func", "cli"])
def test_existing_entity_different_content(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    namespace: str | None,
    call_type: Literal["func", "cli"],
    capsys: pytest.CaptureFixture,
    verbose: bool,
    no_external_calls: bool,
) -> None:
    """Test that the correct conclusion is drawn; that an external entity already exists
    and differs in content.

    When called as a function, ensure this result is returned as expected (when using
    `return_full_info=True`).
    When called as a CLI command, ensure the same result is presented in the output.
    """
    import json
    from copy import deepcopy

    if call_type == "func":
        from entities_service.cli._utils.types import ValidEntity
        from entities_service.cli.commands.validate import validate
    else:
        from entities_service.cli.main import APP

    from entities_service.models import URI_REGEX
    from entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace

    assert "uri" in raw_entity

    if namespace:
        # Update the entity's namespace to the current namespace
        if "namespace" in raw_entity:
            raw_entity["namespace"] = current_namespace
        raw_entity["uri"] = raw_entity["uri"].replace(
            f"{core_namespace}/", f"{current_namespace}/"
        )

        # Write the updated entity to file
        directory = tmp_path / "valid_entities"
        directory.mkdir(parents=True, exist_ok=True)
        entity_filepath = directory / "Person.json"
        entity_filepath.write_text(json.dumps(raw_entity))

    if not no_external_calls:
        # Mock response for "Check if entity already exists"
        httpx_mock.add_response(
            url=raw_entity["uri"],
            status_code=200,  # ok
            json=raw_entity,
        )

    original_uri_match = URI_REGEX.match(raw_entity["uri"])
    assert original_uri_match is not None
    original_uri_match_dict = original_uri_match.groupdict()

    # Create a new file with a change in the content
    new_entity = deepcopy(raw_entity)
    new_entity["dimensions"]["n_skills"] = "Skill number."
    new_entity["namespace"] = original_uri_match_dict["namespace"]
    new_entity["version"] = original_uri_match_dict["version"]
    new_entity["name"] = original_uri_match_dict["name"]
    assert new_entity != raw_entity
    (tmp_path / "Person.json").write_text(json.dumps(new_entity))

    if call_type == "func":
        valid_entity = validate(
            filepaths=[tmp_path / "Person.json"],
            return_full_info=True,
            verbose=verbose,
            no_external_calls=no_external_calls,
        )

        assert isinstance(valid_entity, list)
        assert all(isinstance(entity, ValidEntity) for entity in valid_entity)

        assert len(valid_entity) == 1
        assert (
            valid_entity[0].entity.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            == new_entity
        )

        if no_external_calls:
            assert valid_entity[0].exists_remotely is None
            assert valid_entity[0].equal_to_remote is None
            assert valid_entity[0].pretty_diff is None
        else:
            assert valid_entity[0].exists_remotely is True
            assert valid_entity[0].equal_to_remote is False
            assert valid_entity[0].pretty_diff is not None

        captured = capsys.readouterr()

        stdout, stderr = captured.out, captured.err
    else:
        result = cli.invoke(
            APP,
            f"validate {'--verbose ' if verbose else ''}"
            f"{'--no-external-calls ' if no_external_calls else ''}"
            f"{tmp_path / 'Person.json'}",
        )

        assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        if no_external_calls:
            # THe first 'Unknown' explains that it is unknown whether the entity exists
            # externally.
            # The second 'Unknown' explains that it is unknown whether a possible
            # external entity is equal to the local entity.
            assert (
                f"{namespace if namespace else '/'}{new_entity['name']}"
                f"{new_entity['version']}UnknownUnknown"
                in result.stdout.replace(" ", "")
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )
        else:
            # The 'Yes' explains that the entity already exists externally.
            # The 'No' explains that the entity differs from the remote entity.
            assert (
                f"{namespace if namespace else '/'}{new_entity['name']}"
                f"{new_entity['version']}YesNo" in result.stdout.replace(" ", "")
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )

        stdout, stderr = result.stdout, result.stderr

    # Common assertions
    assert (
        "There were no valid entities among the supplied sources." not in stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)
    assert not stderr, CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)

    detailed_diff_summary = "Detailed differences in validated entities:"
    verbose_info = "Use the option '--verbose' to see the differences"
    if verbose and not no_external_calls:
        assert detailed_diff_summary in stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=stdout, stderr=stderr
        )
        assert verbose_info not in stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=stdout, stderr=stderr
        )

    if not verbose or no_external_calls:
        assert detailed_diff_summary not in stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=stdout, stderr=stderr
        )

    if verbose and no_external_calls:
        assert verbose_info not in stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=stdout, stderr=stderr
        )

    if not verbose and not no_external_calls:
        if call_type == "cli":
            assert verbose_info in stdout, CLI_RESULT_FAIL_MESSAGE.format(
                stdout=stdout, stderr=stderr
            )
        else:
            assert verbose_info not in stdout, CLI_RESULT_FAIL_MESSAGE.format(
                stdout=stdout, stderr=stderr
            )

    if no_external_calls:
        assert (
            "No external calls will be made" in stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)
    else:
        assert (
            "No external calls will be made" not in stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)


def test_http_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    parameterized_entity: ParameterizeGetEntities,
) -> None:
    """Ensure proper error messages are given if an HTTP error occurs."""
    from httpx import HTTPError

    from entities_service.cli.main import APP

    error_message = "Generic HTTP Error"
    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    # Mock response for "Check if entity already exists"
    httpx_mock.add_exception(HTTPError(error_message), url=parameterized_entity.uri)

    result = cli.invoke(APP, f"validate --quiet {test_file}")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not check if entity already exists. HTTP exception: "
        f"{error_message}" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


def test_json_decode_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    parameterized_entity: ParameterizeGetEntities,
) -> None:
    """Ensure proper error messages are given if a JSONDecodeError occurs."""
    from entities_service.cli.main import APP

    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    # Mock response for "Check if entity already exists"
    httpx_mock.add_response(
        url=parameterized_entity.uri, status_code=200, content=b"not json"
    )

    result = cli.invoke(APP, f"validate --quiet {test_file}")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not check if entity already exists. JSON decode error: "
        in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.parametrize("fail_fast", [True, False])
def test_non_unique_uris(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    namespace: str | None,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    """Test that non-unique URIs result in an error."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

    target_directory = tmp_path / "duplicate_uri_entities"
    target_directory.mkdir(parents=True, exist_ok=False)

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace

    assert "uri" in raw_entity

    if namespace:
        # Update entity to the current namespace
        # This is to ensure the same error is given when hitting the specific
        # namespace endpoint
        if "namespace" in raw_entity:
            raw_entity["namespace"] = current_namespace

        raw_entity["uri"] = raw_entity["uri"].replace(
            f"{core_namespace}/", f"{current_namespace}/"
        )

    # Write the entity to file in the target directory
    (target_directory / "Person.json").write_text(json.dumps(raw_entity))

    # Write the same entity to file in the target directory, but with a different
    # file name
    (target_directory / "duplicate.json").write_text(json.dumps(raw_entity))

    if not fail_fast:
        # Mock response for "Check if entity already exists"
        httpx_mock.add_response(
            url=raw_entity["uri"],
            status_code=404,  # not found
        )

    result = cli.invoke(
        APP, f"validate {'--fail-fast ' if fail_fast else ''}{target_directory}"
    )

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Error: Duplicate URI found: {raw_entity['uri']}" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    failure_summary = (
        "Failed to validate one or more entities. See above for more details."
    )

    if fail_fast:
        assert failure_summary not in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
    else:
        ## Failures
        assert failure_summary in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        # Files overview
        assert "Files:" in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
        # Only one of the files will be listed here
        # (the second one, whichever it may be)
        assert (
            f'  {target_directory / "Person.json"}' in result.stderr
            or f'  {target_directory / "duplicate.json"}' in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        if f'  {target_directory / "duplicate.json"}' in result.stderr:
            assert (
                f'  {target_directory / "Person.json"}' not in result.stderr
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )
        elif f'  {target_directory / "Person.json"}' in result.stderr:
            assert (
                f'  {target_directory / "duplicate.json"}' not in result.stderr
            ), CLI_RESULT_FAIL_MESSAGE.format(
                stdout=result.stdout, stderr=result.stderr
            )

        # Entities overview
        assert "Entities:" in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
        assert (
            f"  {raw_entity['uri']}" in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        ## Successes

        # The first entity to be validated will be... valid
        # The 'No' explains that the entity does not exist externally.
        assert (
            f"{namespace if namespace else '/'}Person0.1No-"
            in result.stdout.replace(" ", "")
        ), CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        assert (
            "There were no valid entities among the supplied sources."
            not in result.stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.parametrize("yaml_format", ["yaml", "yml"])
def test_list_of_entities_in_single_file(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    yaml_format: Literal["yaml", "yml"],
) -> None:
    """Test validate with a filepath."""
    import yaml

    from entities_service.cli.main import APP

    entities_filepath = static_dir / "valid_entities.yaml"
    raw_entities: list[dict[str, Any]] = yaml.safe_load(entities_filepath.read_text())

    # Mock response for "Check if entity already exists"
    for raw_entity in raw_entities:
        id_key = "identity" if "identity" in raw_entity else "uri"
        assert id_key in raw_entity
        httpx_mock.add_response(
            url=raw_entity[id_key],
            status_code=404,  # not found
        )

    result = cli.invoke(APP, f"validate --format {yaml_format} {entities_filepath}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.parametrize("fail_fast", [True, False])
def test_bad_list_of_entities_in_single_file(
    cli: CliRunner, static_dir: Path, fail_fast: bool, tmp_path: Path
) -> None:
    """Test validate with a filepath."""
    import yaml

    from entities_service.cli.main import APP

    entities_filepath = static_dir / "valid_entities.yaml"
    raw_entities: list[dict[str, Any]] = yaml.safe_load(entities_filepath.read_text())

    # Add a non-dict to the list
    raw_entities.append("not a dict")

    # Write the updated list of entities to file
    bad_list_of_entities_filepath = tmp_path / "bad_list_of_entities.yaml"
    bad_list_of_entities_filepath.write_text(
        yaml.safe_dump(raw_entities, allow_unicode=True)
    )

    result = cli.invoke(
        APP,
        f"validate {'--fail-fast ' if fail_fast else ''}"
        f"--format=yaml {bad_list_of_entities_filepath}",
    )

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Error: {bad_list_of_entities_filepath}" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "can not be read as either a single or a list of potential SOFT entities."
        in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    assert "Valid Entities" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    failure_summary_text = (
        "Failed to validate one or more entities. See above for more details."
    )
    if fail_fast:
        assert (
            failure_summary_text not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
    else:
        assert failure_summary_text in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        assert (
            result.stdout.replace("\n", "")
            == "There were no valid entities among the supplied sources."
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


def test_file_and_dir_deprecation_warning(cli: CliRunner, static_dir: Path) -> None:
    """Test that a warning is given when a file or a directory option is provided.

    But it should still work.
    """
    from entities_service.cli.main import APP

    directory = static_dir / "valid_entities"
    entity_filepath = directory / "Person.json"

    # file
    result = cli.invoke(APP, f"validate --file {entity_filepath}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Warning: The option '--file/-f' is deprecated. Please, use a SOURCE instead."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # directory
    result = cli.invoke(APP, f"validate --dir {directory}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Warning: The option '--dir/-d' is deprecated. Please, use a SOURCE instead."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


def test_source_is_no_file_or_dir(cli: CliRunner) -> None:
    """Test that an error is given when the source is neither a file nor a directory."""
    from entities_service.cli.main import APP

    result = cli.invoke(APP, "validate /dev/null")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Error: Path '/dev/null' is not a file or directory." in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.parametrize("stdin_variation", ["-", "/dev/stdin", "CON", "CONIN$"])
def test_using_stdin(
    cli: CliRunner,
    static_dir: Path,
    tmp_path: Path,
    stdin_variation: Literal["-", "/dev/stdin", "CON", "CONIN$"],
) -> None:
    """Test that it's possible to pipe in a filepath to validate."""
    from entities_service.cli.main import APP

    valid_entities_dir = static_dir / "valid_entities"

    test_dir = tmp_path / "test_dir"
    test_dir.mkdir(parents=True)
    filepaths = []

    number_of_valid_entities = 0

    for index, filepath in enumerate(valid_entities_dir.glob("*.json")):
        if index % 2 == 0:  # Let's put half in the folder
            test_dir.joinpath(filepath.name).write_text(filepath.read_text())
        else:  # And the other half in a reference
            filepaths.append(filepath)

        number_of_valid_entities += 1

    stdin = "\n".join(str(filepath) for filepath in filepaths)
    stdin += f"\n{test_dir}"

    # Add an extra newline to simulate supplying a file as input, with an empty line at
    # the end. This should be ignored and not result in an error.
    stdin += "\n"

    result = cli.invoke(APP, f"validate {stdin_variation}", input=stdin)

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # There should be "number_of_valid_entities" number of `No` entries in the summary,
    # since none of the entities exist externally.
    assert (
        result.stdout.count("No") == number_of_valid_entities
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.parametrize("fail_fast", [True, False], ids=["fail-fast", "no-fail-fast"])
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose", "no-verbose"])
def test_validate_strict(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    fail_fast: bool,
    verbose: bool,
) -> None:
    """Test validate with the strict option."""
    import json

    from entities_service.cli.main import APP

    directory = static_dir / "valid_entities"

    # We need at least 4 valid entities to make this test meaningful
    assert len(list(directory.glob("*.json"))) >= 4

    file_inputs = ""
    number_existing_changed_entities = 0

    # Mock response for "Check if entity already exists"
    for index, entity in enumerate(
        (json.loads(filepath.read_bytes()), filepath)
        for filepath in directory.glob("*.json")
    ):
        raw_entity, filepath = entity

        file_inputs += f" {filepath}"

        id_key = "identity" if "identity" in raw_entity else "uri"
        assert id_key in raw_entity

        # Let's say half exist externally already
        if index % 2 == 0:
            existing_entity_content = raw_entity.copy()

            if id_key == "identity":
                existing_entity_content["uri"] = existing_entity_content.pop("identity")
                id_key = "uri"

            # And for half of those, let's say they exist with different content
            if index % 4 == 0:
                if isinstance(existing_entity_content["properties"], dict):
                    assert "extra_property" not in existing_entity_content["properties"]
                    existing_entity_content["properties"]["extra_property"] = {
                        "type": "string",
                        "description": "extra property for testing --strict",
                    }
                else:
                    assert isinstance(existing_entity_content["properties"], list)
                    extra_property = {
                        "name": "extra_property",
                        "type": "string",
                        "description": "extra property for testing --strict",
                    }
                    assert extra_property not in existing_entity_content["properties"]
                    existing_entity_content["properties"].append(extra_property)

                number_existing_changed_entities += 1

            httpx_mock.add_response(
                url=existing_entity_content[id_key],
                status_code=200,  # ok
                json=existing_entity_content,
            )

            if fail_fast:
                break

        # While the other half do not exist externally...
        else:
            httpx_mock.add_response(
                url=raw_entity[id_key],
                status_code=404,  # not found
            )

    assert (
        number_existing_changed_entities > 0
    ), "No entities were given 'existing entity with changed content'-role to test."

    result = cli.invoke(
        APP,
        "validate --strict "
        f"{'--fail-fast ' if fail_fast else ''}"
        f"{'--verbose ' if verbose else ''}"
        f"{file_inputs}",
    )

    print(CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr))

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "already exists externally and differs in its contents." in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "There were no valid entities among the supplied sources." not in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if fail_fast:
        assert (
            "Failed to validate one or more entities. See above for more details."
            not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        assert "Valid Entities" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
    else:
        assert (
            "Failed to validate one or more entities. See above for more details."
            in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        assert (
            result.stdout.replace(" ", "")
            .replace("\n", "")
            .count("No(errorinstrict-mode)")
            == number_existing_changed_entities
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if verbose:
        assert "Detailed differences" in (
            result.stderr if fail_fast else result.stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert "Use the option '--verbose'" in (
            result.stderr if fail_fast else result.stdout
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


def test_exclusive_no_external_calls_and_strict(cli: CliRunner) -> None:
    """Test that the exclusive options --no-external-calls and --strict are handled."""
    from entities_service.cli.main import APP

    result = cli.invoke(APP, "validate --no-external-calls --strict /dev/null")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: The options '--no-external-calls' and '--strict' can not be used "
        "together." in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
