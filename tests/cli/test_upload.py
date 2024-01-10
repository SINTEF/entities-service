"""Tests for `entities-service upload` CLI command."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from pytest_httpx import HTTPXMock
    from typer.testing import CliRunner

    from ..conftest import GetBackendUserFixture


pytestmark = pytest.mark.usefixtures("_use_valid_token")

CLI_RESULT_FAIL_MESSAGE = "STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"


def test_upload_no_args(cli: CliRunner) -> None:
    """Test `entities-service upload` CLI command."""
    from dlite_entities_service.cli.main import APP, upload

    result = cli.invoke(APP, "upload")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert upload.__doc__ in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert result.stdout == cli.invoke(APP, "upload --help").stdout


@pytest.mark.usefixtures("_empty_backend_collection")
def test_upload_filepath(
    cli: CliRunner, static_dir: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload with a filepath."""
    import json

    from dlite_entities_service.cli import main
    from dlite_entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

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
        match_headers={"Authorization": "Bearer mock_token"},
        match_json=[raw_entity],
        status_code=201,  # created
    )

    result = cli.invoke(main.APP, f"upload --file {entity_filepath}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Successfully uploaded 1 entity:" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.parametrize("fail_fast", [True, False])
def test_upload_filepath_invalid(
    cli: CliRunner, static_dir: Path, fail_fast: bool
) -> None:
    """Test upload with an invalid filepath."""
    from dlite_entities_service.cli.main import APP

    result = cli.invoke(
        APP,
        f"upload {'--fail-fast ' if fail_fast else ''}"
        f"--file {static_dir / 'invalid_entities' / 'Person.json'}",
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Person.json is not a valid SOFT entity:" in result.stderr.replace("\n", "")
    assert "validation error for SOFT7Entity" in result.stderr.replace("\n", "")
    assert "validation errors for SOFT5Entity" in result.stderr.replace("\n", "")
    assert not result.stdout
    if fail_fast:
        assert (
            "Failed to upload 1 entity, see above for more details:"
            not in result.stderr.replace("\n", "")
        )
    else:
        assert (
            "Failed to upload 1 entity, see above for more details:"
            in result.stderr.replace("\n", "")
        )


def test_upload_filepath_invalid_format(cli: CliRunner, tmp_path: Path) -> None:
    """Test upload with an invalid file format."""
    from dlite_entities_service.cli.main import APP

    (tmp_path / "Person.txt").touch()

    result = cli.invoke(APP, f"upload --file {tmp_path / 'Person.txt'}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert result.stderr.count("File format 'txt' is not supported.") == 1
    assert "No entities were uploaded." in result.stdout


def test_upload_no_file_or_dir(cli: CliRunner) -> None:
    """Test error when no file or directory is provided."""
    from dlite_entities_service.cli.main import APP

    result = cli.invoke(APP, "upload --format json")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Missing either option '--file' / '-f'" in result.stderr.replace("\n", "")
    assert not result.stdout


@pytest.mark.usefixtures("_empty_backend_collection")
def test_upload_directory(
    cli: CliRunner, static_dir: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload with a directory."""
    import json

    from dlite_entities_service.cli import main
    from dlite_entities_service.service.config import CONFIG

    directory = static_dir / "valid_entities"
    raw_entities: list[dict[str, Any]] = [
        json.loads(filepath.read_bytes()) for filepath in directory.glob("*.json")
    ]

    # Mock response for "Check if entity already exists"
    for raw_entity in raw_entities:
        assert "uri" in raw_entity
        httpx_mock.add_response(
            url=raw_entity["uri"],
            status_code=404,  # not found
        )

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_headers={"Authorization": "Bearer mock_token"},
        status_code=201,  # created
    )

    result = cli.invoke(main.APP, f"upload --dir {directory}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Successfully uploaded {len(raw_entities)} entities:"
        in result.stdout.replace("\n", "")
    )


def test_upload_empty_dir(cli: CliRunner, tmp_path: Path) -> None:
    """Test upload with no valid files found.

    The outcome here should be the same whether an empty directory is
    provided or a directory with only invalid files.
    """
    from dlite_entities_service.cli import main

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
        assert "Error: No files found with the given options." in result.stderr.replace(
            "│\n│ ", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
        assert not result.stdout


def test_upload_files_with_unchosen_format(cli: CliRunner, static_dir: Path) -> None:
    """Test upload several files with a format not chosen."""
    from dlite_entities_service.cli.main import APP

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
        f"Skipping file: {filepath}" in result.stdout.replace("\n", "")
        for filepath in directory.glob("*.json")
    )
    assert (
        result.stdout.replace("\n", "").count(
            "Entities using the file format 'json' can be uploaded by adding the "
            "option: --format=json"
        )
        == 1
    )
    assert not result.stderr


@pytest.mark.parametrize("fail_fast", [True, False])
def test_upload_directory_invalid_entities(
    cli: CliRunner, static_dir: Path, fail_fast: bool
) -> None:
    """Test uploading a directory full of invalid entities."""
    import re

    from dlite_entities_service.cli.main import APP

    directory = static_dir / "invalid_entities"

    result = cli.invoke(
        APP, f"upload {'--fail-fast ' if fail_fast else ''}--dir {directory}"
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        re.search(
            r"validation errors? for SOFT7Entity", result.stderr.replace("\n", "")
        )
        is not None
    )
    assert (
        re.search(
            r"validation errors? for SOFT5Entity", result.stderr.replace("\n", "")
        )
        is not None
    )
    assert not result.stdout

    if fail_fast:
        errored_entity = set()
        for invalid_entity in directory.glob("*.json"):
            if (
                f"{invalid_entity.name} is not a valid SOFT entity:"
                in result.stderr.replace("\n", "")
            ):
                errored_entity.add(invalid_entity.name)
        assert len(errored_entity) == 1

        assert (
            f"Failed to upload {len(list(directory.glob('*.json')))} entities, see "
            "above for more details:" not in result.stderr.replace("\n", "")
        )
    else:
        assert all(
            f"{invalid_entity.name} is not a valid SOFT entity:"
            in result.stderr.replace("\n", "")
            for invalid_entity in directory.glob("*.json")
        )

        assert (
            f"Failed to upload {len(list(directory.glob('*.json')))} entities, see "
            "above for more details:" in result.stderr.replace("\n", "")
        )


def test_existing_entity(
    cli: CliRunner, static_dir: Path, httpx_mock: HTTPXMock
) -> None:
    """Test that an existing entity is not overwritten."""
    import json

    from dlite_entities_service.cli.main import APP

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

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
    assert "Entity already exists in the database." in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "No entities were uploaded." in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr


def test_existing_entity_different_content(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
) -> None:
    """Test that an incoming entity can be uploaded with a new version due to an
    existance collision."""
    import json
    from copy import deepcopy

    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.models import URI_REGEX
    from dlite_entities_service.service.config import CONFIG

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

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
        "Entity already exists in the database, but they differ in their content."
        in result.stdout.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping file:" in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "No entities were uploaded." in result.stdout.replace(
        "\n", ""
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
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_headers={"Authorization": "Bearer mock_token"},
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
        "Entity already exists in the database, but they differ in their content."
        in result.stdout.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping file:" not in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Successfully uploaded 1 entity:" in result.stdout.replace(
        "\n", ""
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
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_headers={"Authorization": "Bearer mock_token"},
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
        "Entity already exists in the database, but they differ in their content."
        in result.stdout.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping file:" not in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Successfully uploaded 1 entity:" in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr


@pytest.mark.parametrize("fail_fast", [True, False])
def test_existing_entity_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    fail_fast: bool,
) -> None:
    """Test that an incoming entity with existing URI is correctly aborted in certain
    cases."""
    import json
    from copy import deepcopy

    from dlite_entities_service.cli.main import APP

    entity_filepath = static_dir / "valid_entities" / "Person.json"
    raw_entity: dict[str, Any] = json.loads(entity_filepath.read_bytes())

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
        "Entity already exists in the database, but they differ in their content."
        in result.stdout.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping file:" not in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "New version (0.1) is the same as the existing version (0.1)."
        in result.stderr.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if fail_fast:
        assert "Failed to upload 1 entity" not in result.stderr.replace(
            "\n", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert "Failed to upload 1 entity" in result.stderr.replace(
            "\n", ""
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
        "Entity already exists in the database, but they differ in their content."
        in result.stdout.replace("\n", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Skipping file:" not in result.stdout.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "New version (v0.1) is not a valid SOFT version." in result.stderr.replace(
        "\n", ""
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    if fail_fast:
        assert "Failed to upload 1 entity" not in result.stderr.replace(
            "\n", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    else:
        assert "Failed to upload 1 entity" in result.stderr.replace(
            "\n", ""
        ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.no_token()
def test_missing_auth_token(cli: CliRunner, static_dir: Path) -> None:
    """Ensure an error is thrown if the user has not logged in."""
    from dlite_entities_service.cli.main import APP

    result = cli.invoke(APP, f"upload --dir {static_dir / 'valid_entities'}")
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Missing authorization token. Please login first by running "
        "'entities-service login'." in result.stderr.replace("\n", "")
    )
    assert not result.stdout


@pytest.mark.skip_if_live_backend("Does not raise HTTP errors in this case.")
def test_http_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    random_valid_entity: dict[str, Any],
) -> None:
    """Ensure proper error messages are given if an HTTP error occurs."""
    from httpx import HTTPError

    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    error_message = "Generic HTTP Error"

    if "uri" in random_valid_entity:
        entity_uri: str = random_valid_entity["uri"]
        entity_name: str = entity_uri.split("/")[-1]
    else:
        entity_uri = (
            f"{random_valid_entity['namespace']}/{random_valid_entity['version']}"
            f"/{random_valid_entity['name']}"
        )
        entity_name = random_valid_entity["name"]

    # Mock response for "Check if entity already exists"
    httpx_mock.add_exception(HTTPError(error_message), url=entity_uri)

    result = cli.invoke(
        APP,
        (
            "upload --file "
            f"{(static_dir / 'valid_entities' / entity_name).with_suffix('.json')}"
        ),
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not check if entity already exists. HTTP exception: "
        f"{error_message}" in result.stderr.replace("\n", "")
    )
    assert not result.stdout

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=entity_uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )
    httpx_mock.add_exception(
        HTTPError(error_message),
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
    )

    result = cli.invoke(
        APP,
        (
            "upload --file "
            f"{(static_dir / 'valid_entities' / entity_name).with_suffix('.json')}"
        ),
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Error: Could not upload entity. HTTP exception: {error_message}"
        in result.stderr.replace("\n", "")
    )
    assert not result.stdout


@pytest.mark.skip_if_live_backend("Does not raise JSON decode errors in this case.")
def test_json_decode_errors(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    random_valid_entity: dict[str, Any],
) -> None:
    """Ensure proper error messages are given if a JSONDecodeError occurs."""
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.service.config import CONFIG

    if "uri" in random_valid_entity:
        entity_uri: str = random_valid_entity["uri"]
        entity_name: str = entity_uri.split("/")[-1]
    else:
        entity_uri = (
            f"{random_valid_entity['namespace']}/{random_valid_entity['version']}"
            f"/{random_valid_entity['name']}"
        )
        entity_name = random_valid_entity["name"]

    # Mock response for "Check if entity already exists"
    httpx_mock.add_response(url=entity_uri, status_code=200, content=b"not json")

    result = cli.invoke(
        APP,
        (
            "upload --file "
            f"{(static_dir / 'valid_entities' / entity_name).with_suffix('.json')}"
        ),
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not check if entity already exists. JSON decode error: "
        in result.stderr.replace("\n", "")
    )
    assert not result.stdout

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=entity_uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=400,
        content=b"not json",
    )

    result = cli.invoke(
        APP,
        (
            "upload --file "
            f"{(static_dir / 'valid_entities' / entity_name).with_suffix('.json')}"
        ),
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Error: Could not upload entity. JSON decode error: "
        in result.stderr.replace("\n", "")
    )
    assert not result.stdout


@pytest.mark.no_token()
def test_unable_to_upload(
    cli: CliRunner,
    static_dir: Path,
    httpx_mock: HTTPXMock,
    random_valid_entity: dict[str, Any],
) -> None:
    """Ensure a proper error message is given if an entity cannot be uploaded."""
    import json

    from dlite_entities_service.cli._utils.global_settings import CONTEXT
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.models.auth import Token
    from dlite_entities_service.service.config import CONFIG

    if "uri" in random_valid_entity:
        entity_uri: str = random_valid_entity["uri"]
        entity_name: str = entity_uri.split("/")[-1]
    else:
        entity_uri = (
            f"{random_valid_entity['namespace']}/{random_valid_entity['version']}"
            f"/{random_valid_entity['name']}"
        )
        entity_name = random_valid_entity["name"]

    assert CONTEXT["token"] is None
    CONTEXT["token"] = Token(access_token="bad_token")

    error_message = {"detail": "Could not validate credentials. Please log in."}

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=entity_uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=401,
        json=error_message,
    )

    result = cli.invoke(
        APP,
        (
            "upload --file "
            f"{(static_dir / 'valid_entities' / entity_name).with_suffix('.json')}"
        ),
    )
    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    dumped_error_message = json.dumps(error_message, separators=(",", ":")).replace(
        '"', "'"
    )
    assert (
        "Error: Could not upload entity. HTTP status code: 401. Error message: "
        f"{dumped_error_message}" in result.stderr.replace("\n", "")
    )
    assert not result.stdout


@pytest.mark.no_token()
@pytest.mark.usefixtures("_empty_backend_collection")
def test_global_option_token(
    cli: CliRunner,
    static_dir: Path,
    random_valid_entity: dict[str, Any],
    httpx_mock: HTTPXMock,
    live_backend: bool,
    get_backend_user: GetBackendUserFixture,
) -> None:
    """Test that the token is correctly used when supplied using `--token`."""
    from httpx import Client

    from dlite_entities_service.cli._utils.global_settings import CONTEXT
    from dlite_entities_service.cli.main import APP
    from dlite_entities_service.models.auth import Token
    from dlite_entities_service.service.config import CONFIG

    if "uri" in random_valid_entity:
        entity_uri: str = random_valid_entity["uri"]
        entity_name: str = entity_uri.split("/")[-1]
    else:
        entity_uri = (
            f"{random_valid_entity['namespace']}/{random_valid_entity['version']}"
            f"/{random_valid_entity['name']}"
        )
        entity_name = random_valid_entity["name"]

    assert CONTEXT["token"] is None

    # Mock response for "Check if entity already exists"
    httpx_mock.add_response(
        url=entity_uri,
        status_code=404,  # not found
    )

    if live_backend:
        # Get token
        write_access_user = get_backend_user("readWrite")

        with Client(base_url=str(CONFIG.base_url)) as client:
            response = client.post(
                "/_auth/token",
                data={
                    "grant_type": "password",
                    "username": write_access_user["username"],
                    "password": write_access_user["password"],
                },
            )

        token = Token(**response.json())
    else:
        # Mock token
        token = Token(access_token="mock_token")

        # Mock response for "Upload entities"
        httpx_mock.add_response(
            url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
            method="POST",
            match_headers={"Authorization": f"{token.token_type} {token.access_token}"},
            match_json=[random_valid_entity],
            status_code=201,  # created
        )

    result = cli.invoke(
        APP,
        f"--token {token.access_token} upload --file "
        f"{(static_dir / 'valid_entities' / entity_name).with_suffix('.json')}",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Successfully uploaded 1 entity:" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr

    assert CONTEXT["token"] == token
