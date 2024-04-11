"""Tests for `entities-service upload` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from pytest_httpx import HTTPXMock
    from typer.testing import CliRunner

    from ..conftest import ParameterizeGetEntities

pytestmark = pytest.mark.skip_if_live_backend("OAuth2 verification cannot be mocked.")

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


def test_upload_no_args(cli: CliRunner) -> None:
    """Test `entities-service upload` CLI command."""
    from entities_service.cli.commands.upload import upload
    from entities_service.cli.main import APP

    result = cli.invoke(APP, "upload")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert upload.__doc__ in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert result.stdout == cli.invoke(APP, "upload --help").stdout


@pytest.mark.usefixtures("_empty_backend_collection", "_mock_successful_oauth_response")
def test_upload_filepath(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    token_mock: str,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test upload with a filepath."""
    import json

    from entities_service.cli import main
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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    assert "uri" in raw_entity
    httpx_mock.add_response(
        url=raw_entity["uri"],
        status_code=404,  # not found
    )

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_headers={"Authorization": f"Bearer {token_mock}"},
        match_json=[raw_entity],
        status_code=201,  # created
    )

    result = cli.invoke(main.APP, f"upload --file {entity_filepath}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Successfully uploaded 1 entity" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.parametrize("fail_fast", [True, False])
@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_filepath_invalid(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    httpx_mock: HTTPXMock,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test upload with an invalid filepath."""
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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        status_code=204,
        match_json=[],
    )

    result = cli.invoke(
        APP,
        f"upload {'--fail-fast ' if fail_fast else ''}"
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
    if fail_fast:
        assert not result.stdout
        assert (
            "Failed to upload 1 entity, see above for more details:"
            not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert (
            result.stdout.replace("\n", "")
            == "There were no valid entities among the supplied sources."
        )
        assert (
            "Failed to validate one or more entities. See above for more details."
            in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_filepath_invalid_format(
    cli: CliRunner, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload with an invalid file format."""
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    (tmp_path / "Person.txt").touch()

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    result = cli.invoke(APP, f"upload --file {tmp_path / 'Person.txt'}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert result.stderr.count("File format 'txt' is not supported.") == 1
    assert "No entities were uploaded." in result.stdout


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_no_file_or_dir(cli: CliRunner, httpx_mock: HTTPXMock) -> None:
    """Test error when no file or directory is provided."""
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    result = cli.invoke(APP, "upload --format json")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Missing either option '--file' / '-f'" in result.stderr
    assert not result.stdout


@pytest.mark.usefixtures("_empty_backend_collection", "_mock_successful_oauth_response")
def test_upload_directory(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    token_mock: str,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test upload with a directory."""
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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    for raw_entity in raw_entities:
        assert "uri" in raw_entity
        httpx_mock.add_response(
            url=raw_entity["uri"],
            status_code=404,  # not found
        )

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        method="POST",
        match_headers={"Authorization": f"Bearer {token_mock}"},
        status_code=201,  # created
    )

    result = cli.invoke(main.APP, f"upload --dir {directory}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert f"Successfully uploaded {len(raw_entities)} entities" in result.stdout


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_empty_dir(
    cli: CliRunner, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload with no valid files found.

    The outcome here should be the same whether an empty directory is
    provided or a directory with only invalid files.
    """
    from entities_service.cli import main
    from entities_service.service.config import CONFIG

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    empty_dir = tmp_path / "empty_dir"
    assert not empty_dir.exists()
    empty_dir.mkdir()

    yaml_dir = tmp_path / "yaml_dir"
    assert not yaml_dir.exists()
    yaml_dir.mkdir()
    (yaml_dir / "Person.yaml").touch()

    for directory in (empty_dir, yaml_dir):
        result = cli.invoke(main.APP, f"upload --format json --dir {directory}")
        assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
            stdout=result.stdout, stderr=result.stderr
        )
        assert (
            "Error: No files found with the given options." in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        assert not result.stdout


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_files_with_unchosen_format(
    cli: CliRunner, static_dir: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload several files with a format not chosen."""
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    directory = static_dir / "valid_entities"
    file_inputs = " ".join(
        f"--file={filepath}" for filepath in directory.glob("*.json")
    )

    result = cli.invoke(APP, f"upload --format yaml {file_inputs}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "No entities were uploaded." in result.stdout
    assert all(
        f"Skipping file: ./{filepath.relative_to(static_dir.parent.parent.resolve())}"
        in result.stdout.replace("\n", "")
        for filepath in directory.glob("*.json")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        result.stdout.replace("\n", "").count(
            "Entities using the file format 'json' can be uploaded by adding the "
            "option: --format=json"
        )
        == 1
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr


@pytest.mark.parametrize("fail_fast", [True, False])
@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_directory_invalid_entities(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    httpx_mock: HTTPXMock,
    namespace: str | None,
    tmp_path: Path,
) -> None:
    """Test uploading a directory full of invalid entities.

    This test ensures all invalid entities are recognized and reported prior to any
    attempts to upload.
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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    result = cli.invoke(
        APP, f"upload {'--fail-fast ' if fail_fast else ''}--dir {directory}"
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
            f"Failed to upload {len(list(directory.glob('*.json')))} entities, see "
            "above for more details:" not in result.stderr
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

        assert (
            "Failed to validate one or more entities. See above for more details."
            in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_existing_entity(
    cli: CliRunner, static_dir: Path, httpx_mock: HTTPXMock
) -> None:
    """Test that an existing entity is not overwritten."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    assert "uri" in raw_entity
    httpx_mock.add_response(
        url=raw_entity["uri"],
        status_code=200,  # ok
        json=raw_entity,
    )

    result = cli.invoke(APP, f"upload --file {entity_filepath}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Entity already exists externally." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "No entities were uploaded." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_existing_entity_different_content(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    token_mock: str,
    namespace: str | None,
) -> None:
    """Test that an incoming entity can be uploaded with a new version due to an
    existence collision."""
    import json
    from copy import deepcopy

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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        status_code=204,
        match_json=[],
    )

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

    # First, let's check we skip the file if not wanting to update the version
    result = cli.invoke(
        APP,
        f"upload --file {tmp_path / 'Person.json'}",
        input="n\n",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Entity already exists externally, but it differs in its content."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping entity:" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "No entities were uploaded." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr

    # Now, let's check we update the version if wanting to.
    # Use default generated version. An existing version of '0.1' should generate
    # '0.1.1'.

    # Mock response for "Upload entities"
    new_entity_file_to_be_uploaded = deepcopy(new_entity)
    new_entity_file_to_be_uploaded["version"] = "0.1.1"
    new_entity_file_to_be_uploaded["uri"] = (
        f"{original_uri_match_dict['namespace']}/0.1.1"
        f"/{original_uri_match_dict['name']}"
    )
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        method="POST",
        match_headers={"Authorization": f"Bearer {token_mock}"},
        match_json=[new_entity_file_to_be_uploaded],
        status_code=201,  # created
    )

    result = cli.invoke(
        APP,
        f"upload --file {tmp_path / 'Person.json'}",
        input="y\n\n",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Entity already exists externally, but it differs in its content."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping entity:" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Successfully uploaded 1 entity" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr

    # Now, let's check we update the version if wanting to.
    # Use custom version.

    custom_version = "0.2"

    # Mock response for "Upload entities"
    new_entity_file_to_be_uploaded = deepcopy(new_entity)
    new_entity_file_to_be_uploaded["version"] = custom_version
    new_entity_file_to_be_uploaded["uri"] = (
        f"{original_uri_match_dict['namespace']}/{custom_version}"
        f"/{original_uri_match_dict['name']}"
    )
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        method="POST",
        match_headers={"Authorization": f"Bearer {token_mock}"},
        match_json=[new_entity_file_to_be_uploaded],
        status_code=201,  # created
    )

    result = cli.invoke(
        APP,
        f"upload --file {tmp_path / 'Person.json'}",
        input=f"y\n{custom_version}\n",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Entity already exists externally, but it differs in its content."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping entity:" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Successfully uploaded 1 entity" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr


@pytest.mark.parametrize("fail_fast", [True, False])
@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_existing_entity_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    fail_fast: bool,
    namespace: str | None,
) -> None:
    """Test that an incoming entity with existing URI is correctly aborted in certain
    cases."""
    import json
    from copy import deepcopy

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
        directory = tmp_path / "valid_entities"
        directory.mkdir(parents=True, exist_ok=True)
        entity_filepath = directory / "Person.json"
        entity_filepath.write_text(json.dumps(raw_entity))

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    assert "uri" in raw_entity
    httpx_mock.add_response(
        url=raw_entity["uri"],
        status_code=200,  # ok
        json=raw_entity,
    )

    # Create a new file with a change in the content
    new_entity = deepcopy(raw_entity)
    new_entity["dimensions"]["n_skills"] = "Skill number."
    assert new_entity != raw_entity
    new_entity_file = tmp_path / "Person.json"
    new_entity_file.write_text(json.dumps(new_entity))

    # Let's check an error occurs if the version change is to the existing version.
    # The existing version is '0.1'.
    result = cli.invoke(
        APP,
        f"upload {'--fail-fast ' if fail_fast else ''}"
        f"--file {tmp_path / 'Person.json'}",
        input="y\n0.1\n",
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Entity already exists externally, but it differs in its content."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping entity:" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "New version (0.1) is the same as the existing version." in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if fail_fast:
        assert (
            "Failed to upload 1 entity" not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert (
            "Failed to upload 1 entity" in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    # Let's check an error occurs if the version is not of the type MAJOR.MINOR.PATCH.
    result = cli.invoke(
        APP,
        f"upload {'--fail-fast ' if fail_fast else ''}"
        f"--file {tmp_path / 'Person.json'}",
        input="y\nv0.1\n",
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "Entity already exists externally, but it differs in its content."
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping entity:" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "New version (v0.1) is not a valid SOFT version." in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if fail_fast:
        assert (
            "Failed to upload 1 entity" not in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert (
            "Failed to upload 1 entity" in result.stderr
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_http_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    parameterized_entity: ParameterizeGetEntities,
) -> None:
    """Ensure proper error messages are given if an HTTP error occurs."""
    from httpx import HTTPError

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    error_message = "Generic HTTP Error"
    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    httpx_mock.add_exception(HTTPError(error_message), url=parameterized_entity.uri)

    result = cli.invoke(APP, f"upload --quiet --file {test_file}")
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

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=parameterized_entity.uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )
    httpx_mock.add_exception(
        HTTPError(error_message),
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        match_json=[parameterized_entity.backend_entity],
    )

    result = cli.invoke(APP, f"upload --quiet --file {test_file}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Error: Could not upload entity. HTTP exception: {error_message}"
        in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_json_decode_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    parameterized_entity: ParameterizeGetEntities,
) -> None:
    """Ensure proper error messages are given if a JSONDecodeError occurs."""
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    httpx_mock.add_response(
        url=parameterized_entity.uri, status_code=200, content=b"not json"
    )

    result = cli.invoke(APP, f"upload --quiet --file {test_file}")
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

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=parameterized_entity.uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=400,
        content=b"not json",
        match_json=[parameterized_entity.backend_entity],
    )

    result = cli.invoke(APP, f"upload --quiet --file {test_file}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not upload entity. JSON decode error: " in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_unable_to_upload(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    parameterized_entity: ParameterizeGetEntities,
) -> None:
    """Ensure a proper error message is given if an entity cannot be uploaded."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    error_message = {"detail": "Could not validate credentials. Please log in."}
    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=401,
        json=error_message,
    )

    result = cli.invoke(APP, f"upload --file {test_file}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    dumped_error_message = json.dumps(error_message)
    assert (
        "Error: Could not login. HTTP status code: 401. Error response: "
        f"{dumped_error_message}" in result.stderr.replace("\n", "").replace("  ", "")
    )
    assert not result.stdout


@pytest.mark.parametrize("fail_fast", [True, False])
@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_non_unique_uris(
    cli: CliRunner,
    static_dir: Path,
    fail_fast: bool,
    httpx_mock: HTTPXMock,
    namespace: str | None,
    tmp_path: Path,
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

    if namespace:
        # Update entity to the current namespace
        # This is to ensure the same error is given when hitting the specific
        # namespace endpoint
        if "namespace" in raw_entity:
            raw_entity["namespace"] = current_namespace
        if "uri" in raw_entity:
            raw_entity["uri"] = raw_entity["uri"].replace(
                f"{core_namespace}/", f"{current_namespace}/"
            )

    # Write the entity to file in the target directory
    (target_directory / "Person.json").write_text(json.dumps(raw_entity))

    # Write the same entity to file in the target directory, but with a different
    # file name
    (target_directory / "duplicate.json").write_text(json.dumps(raw_entity))

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        status_code=204,
        match_json=[],
    )

    result = cli.invoke(
        APP, f"upload {'--fail-fast ' if fail_fast else ''}--dir {target_directory}"
    )

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    uri = raw_entity.get("uri") or (
        f"{raw_entity.get('namespace', '')}"
        f"/{raw_entity.get('version', ')')}/{raw_entity.get('name', '')}"
    )
    assert (
        f"Error: Duplicate URI found: {uri}" in result.stderr
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
