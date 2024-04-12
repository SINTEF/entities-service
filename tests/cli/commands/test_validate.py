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


def test_validate_filepath(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test validate with a filepath."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

    core_namespace = str(CONFIG.base_url).rstrip("/")
    current_namespace = f"{core_namespace}/{namespace}" if namespace else core_namespace

    if namespace:
        # Update the entity's namespace to the current namespace
        if "namespace" in raw_entity:
            raw_entity["namespace"] = current_namespace
        if "uri" in raw_entity:
            raw_entity["uri"] = raw_entity["uri"].replace(
                f"{core_namespace}/", f"{current_namespace}/"
            )
        # Write the updated entity to file
        entity_filepath = tmp_path / "Person.json"
        entity_filepath.write_text(json.dumps(raw_entity))

    # Mock response for "Check if entity already exists"
    assert "uri" in raw_entity
    httpx_mock.add_response(
        url=raw_entity["uri"],
        status_code=404,  # not found
    )

    result = cli.invoke(APP, f"validate --file {entity_filepath}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.parametrize("fail_fast", [True, False])
def test_validate_filepath_invalid(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    namespace: str | None,
    tmp_path: Path,
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
        f"validate {'--fail-fast ' if fail_fast else ''}"
        f"--file {invalid_entity_filepath}",
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
        assert (
            result.stdout.replace("\n", "")
            == "There were no valid entities among the supplied sources."
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        assert failure_summary_text in result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )


def test_validate_filepath_invalid_format(cli: CliRunner, tmp_path: Path) -> None:
    """Test validate with an invalid file format."""
    from entities_service.cli.main import APP

    (tmp_path / "Person.txt").touch()

    result = cli.invoke(APP, f"validate --file {tmp_path / 'Person.txt'}")
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


def test_validate_no_file_or_dir(cli: CliRunner) -> None:
    """Test error when no file or directory is provided."""
    from entities_service.cli.main import APP

    result = cli.invoke(APP, "validate --format json")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Missing either option '--file' / '-f'" in result.stderr
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
            if "namespace" in raw_entity:
                raw_entity["namespace"] = current_namespace
            if "uri" in raw_entity:
                raw_entity["uri"] = raw_entity["uri"].replace(
                    f"{core_namespace}/", f"{current_namespace}/"
                )

            # Write the updated entity to file
            (directory / f"{index}.json").write_text(json.dumps(raw_entity))

    # Mock response for "Check if entity already exists"
    for raw_entity in raw_entities:
        assert "uri" in raw_entity
        httpx_mock.add_response(
            url=raw_entity["uri"],
            status_code=404,  # not found
        )

    result = cli.invoke(main.APP, f"validate --dir {directory}")

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
        result = cli.invoke(main.APP, f"validate --format json --dir {directory}")

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
    file_inputs = " ".join(
        f"--file={filepath}" for filepath in directory.glob("*.json")
    )

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
            if "namespace" in invalid_entity:
                invalid_entity["namespace"] = invalid_entity["namespace"].replace(
                    core_namespace, current_namespace
                )
            if "uri" in invalid_entity:
                invalid_entity["uri"] = invalid_entity["uri"].replace(
                    f"{core_namespace}/", f"{current_namespace}/"
                )

            # Write the updated entity to file
            (directory / filepath.name).write_text(json.dumps(invalid_entity))

    result = cli.invoke(
        APP, f"validate {'--fail-fast ' if fail_fast else ''}--dir {directory}"
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


@pytest.mark.parametrize("call_type", ["func", "cli"])
def test_existing_entity(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    capsys: pytest.CaptureFixture,
    call_type: Literal["func", "cli"],
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

    # Mock response for "Check if entity already exists"
    assert "uri" in raw_entity
    httpx_mock.add_response(
        url=raw_entity["uri"],
        status_code=200,  # ok
        json=raw_entity,
    )

    if call_type == "func":
        valid_entity = validate(filepaths=[entity_filepath], return_full_info=True)

        assert isinstance(valid_entity, list)
        assert all(isinstance(entity, ValidEntity) for entity in valid_entity)

        assert len(valid_entity) == 1
        assert (
            valid_entity[0].entity.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            == raw_entity
        )
        assert valid_entity[0].exists_remotely is True
        assert valid_entity[0].equal_to_remote is True
        assert valid_entity[0].pretty_diff is None

        captured = capsys.readouterr()

        stdout, stderr = captured.out, captured.err
    else:
        result = cli.invoke(APP, f"validate --file {entity_filepath}")

        assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        # The first 'Yes' explains that the entity already exists externally.
        # The second 'Yes' explains that the entity is equal to the remote entity.
        assert "/Person0.1YesYes" in result.stdout.replace(
            " ", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        stdout, stderr = result.stdout, result.stderr

    # Common assertions
    assert (
        "There were no valid entities among the supplied sources." not in stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)
    assert not stderr, CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)


@pytest.mark.parametrize("call_type", ["func", "cli"])
def test_existing_entity_different_content(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    namespace: str | None,
    call_type: Literal["func", "cli"],
    capsys: pytest.CaptureFixture,
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

    if namespace:
        # Update the entity's namespace to the current namespace
        if "namespace" in raw_entity:
            raw_entity["namespace"] = current_namespace
        if "uri" in raw_entity:
            raw_entity["uri"] = raw_entity["uri"].replace(
                f"{core_namespace}/", f"{current_namespace}/"
            )

        # Write the updated entity to file
        directory = tmp_path / "valid_entities"
        directory.mkdir(parents=True, exist_ok=True)
        entity_filepath = directory / "Person.json"
        entity_filepath.write_text(json.dumps(raw_entity))

    # Mock response for "Check if entity already exists"
    assert "uri" in raw_entity
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
            filepaths=[tmp_path / "Person.json"], return_full_info=True
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
        assert valid_entity[0].exists_remotely is True
        assert valid_entity[0].equal_to_remote is False
        assert valid_entity[0].pretty_diff is not None

        captured = capsys.readouterr()

        stdout, stderr = captured.out, captured.err
    else:
        result = cli.invoke(
            APP,
            f"validate --file {tmp_path / 'Person.json'}",
        )

        assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )

        # The 'Yes' explains that the entity already exists externally.
        # The 'No' explains that the entity differs from the remote entity.
        assert (
            f"{namespace if namespace else '/'}{new_entity['name']}"
            f"{new_entity['version']}YesNo" in result.stdout.replace(" ", "")
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

        stdout, stderr = result.stdout, result.stderr

    # Common assertions
    assert (
        "There were no valid entities among the supplied sources." not in stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)
    assert not stderr, CLI_RESULT_FAIL_MESSAGE.format(stdout=stdout, stderr=stderr)


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

    result = cli.invoke(APP, f"validate --quiet --file {test_file}")

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

    result = cli.invoke(APP, f"validate --quiet --file {test_file}")

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

    from entities_service.cli.commands.config import CONFIG
    from entities_service.cli.main import APP

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
        APP, f"validate {'--fail-fast ' if fail_fast else ''}--dir {target_directory}"
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
