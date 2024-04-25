"""Tests for `entities-service upload` CLI command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

    from pytest_httpx import HTTPXMock
    from typer.testing import CliRunner

    from ...conftest import ParameterizeGetEntities

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
    """Test upload with a filepath.

    Additionally test nothing is uploaded if the user decides to now upload.
    """
    import json

    from entities_service.cli import main
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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{core_namespace}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
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

    result = cli.invoke(main.APP, f"upload {entity_filepath}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        "Successfully uploaded 1 entity" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    ## Additionally test nothing is uploaded if user decides to not upload.
    result = cli.invoke(main.APP, f"upload {entity_filepath}", input="n\n")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert "Succesfully uploaded" not in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "No entities were uploaded." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_filepath_invalid_format(
    cli: CliRunner, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload with an invalid file format.

    The validation is done in the `validate` command/function.
    The test is here to also ensure the correct summary is printed for the `upload`
    command.
    """
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    (tmp_path / "Person.txt").touch()

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    result = cli.invoke(APP, f"upload {tmp_path / 'Person.txt'}")
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert result.stderr.count("File format 'txt' is not supported.") == 1
    assert "No entities were uploaded." in result.stdout


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

    result = cli.invoke(main.APP, f"upload {directory}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    assert (
        f"Successfully uploaded {len(raw_entities)} entities" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_mock_successful_oauth_response")
def test_upload_files_with_unchosen_format(
    cli: CliRunner, static_dir: Path, httpx_mock: HTTPXMock
) -> None:
    """Test upload several files with a non-chosen format.

    The validation is done in the `validate` command/function.
    The test is here to also ensure the correct summary is printed for the `upload`
    command.
    """
    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    directory = static_dir / "valid_entities"
    file_inputs = " ".join(str(filepath) for filepath in directory.glob("*.json"))

    result = cli.invoke(APP, f"upload --format yaml {file_inputs}")

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        "No entities were uploaded." in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


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

    result = cli.invoke(APP, f"upload {entity_filepath}")
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
        f"upload {tmp_path / 'Person.json'}",
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
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

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
        f"upload {tmp_path / 'Person.json'}",
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
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # Now let's check we get the same result if setting `quiet=True` and not providing
    # input, since the previous input equals the general defaults.
    result = cli.invoke(
        APP,
        f"upload {tmp_path / 'Person.json'} --quiet",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # Now let's check we get the same result if setting `quiet=False` and
    # `auto_confirm=True` and not providing other input, since the previous input
    # (still) equals the general defaults.
    # Here would should get some outputs, however.
    result = cli.invoke(
        APP,
        f"upload {tmp_path / 'Person.json'} --auto-confirm",
    )
    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    # Ensure no confirmations or prompts are in the output
    assert (
        "You cannot overwrite external existing entities. Do you wish to upload the "
        "new entity with an updated version number?" not in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "These entities will be uploaded. Do you want to continue?" not in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        "Please enter the new version" not in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    # Ensure specific `quiet=False` and `auto_confirm=True` outputs are in the output
    assert (
        "Info: Updating the to-be-uploaded entity to specified version:"
        in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert "Entities to upload" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

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
        f"upload {tmp_path / 'Person.json'}",
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
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )


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
        f"upload {'--fail-fast ' if fail_fast else ''}" f"{tmp_path / 'Person.json'}",
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
        f"upload {'--fail-fast ' if fail_fast else ''}" f"{tmp_path / 'Person.json'}",
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

    result = cli.invoke(APP, f"upload --quiet {test_file}")
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

    result = cli.invoke(APP, f"upload --quiet {test_file}")
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

    result = cli.invoke(APP, f"upload --quiet {test_file}")
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

    result = cli.invoke(APP, f"upload --quiet {test_file}")
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

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    httpx_mock.add_response(
        url=parameterized_entity.uri,
        status_code=404,  # not found, i.e., entity does not already exist
    )

    error_status_code = 400
    error_message = {"error": "Could not upload entity."}
    test_file = (static_dir / "valid_entities" / parameterized_entity.name).with_suffix(
        ".json"
    )

    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=error_status_code,
        json=error_message,
        match_json=[parameterized_entity.backend_entity],
    )

    result = cli.invoke(APP, f"upload {test_file}")

    assert result.exit_code == 1, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # Everything up until the very last check should be successful
    assert (
        f"/{parameterized_entity.name}{parameterized_entity.version}No-"
        in result.stdout.replace(" ", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert (
        f"/{parameterized_entity.name}(v{parameterized_entity.version})"
        in result.stdout.replace(" ", "")
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)

    dumped_error_message = json.dumps(error_message)
    assert (
        f"Error: Could not upload entity. HTTP status code: {error_status_code}. "
        f"Error message: "
        f"{dumped_error_message}"
        in result.stderr.replace("\n", "").replace("  ", "").replace("'", '"')
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)


@pytest.mark.usefixtures("_empty_backend_collection", "_mock_successful_oauth_response")
@pytest.mark.parametrize("stdin_variation", ["-", "/dev/stdin", "CON", "CONIN$"])
def test_using_stdin(
    cli: CliRunner,
    static_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
    token_mock: str,
    stdin_variation: Literal["-", "/dev/stdin", "CON", "CONIN$"],
) -> None:
    """Test that it's possible to pipe in a filepath to validate."""
    import json

    from entities_service.cli.main import APP
    from entities_service.service.config import CONFIG

    valid_entities_dir = static_dir / "valid_entities"
    entity_uris: list[str] = [
        json.loads(filepath.read_text())["uri"]
        for filepath in valid_entities_dir.glob("*.json")
    ]

    test_dir = tmp_path / "test_dir"
    test_dir.mkdir(parents=True)
    filepaths = []

    number_of_valid_entities = len(entity_uris)

    for index, filepath in enumerate(valid_entities_dir.glob("*.json")):
        if index % 2 == 0:  # Let's put half in the folder
            test_dir.joinpath(filepath.name).write_text(filepath.read_text())
        else:  # And the other half in a reference
            filepaths.append(filepath)

    stdin = "\n".join(str(filepath) for filepath in filepaths)
    stdin += f"\n{test_dir}"

    # Mock a good login check
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        status_code=204,
        match_json=[],
    )

    # Mock response for "Check if entity already exists"
    for entity_uri in entity_uris:
        httpx_mock.add_response(
            url=entity_uri,
            status_code=404,  # not found
        )

    # Mock response for "Upload entities"
    httpx_mock.add_response(
        url=f"{str(CONFIG.base_url).rstrip('/')}/_admin/create",
        method="POST",
        match_headers={"Authorization": f"Bearer {token_mock}"},
        status_code=201,  # created
    )

    result = cli.invoke(APP, f"upload {stdin_variation}", input=stdin)

    assert result.exit_code == 0, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert "Valid Entities" in result.stdout, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )
    assert (
        f"Successfully uploaded {number_of_valid_entities} entities" in result.stdout
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
    assert not result.stderr, CLI_RESULT_FAIL_MESSAGE.format(
        stdout=result.stdout, stderr=result.stderr
    )

    # There should be "number_of_valid_entities" number of `No` entries in the summary,
    # since none of the entities exist externally.
    assert (
        result.stdout.count("No") == number_of_valid_entities
    ), CLI_RESULT_FAIL_MESSAGE.format(stdout=result.stdout, stderr=result.stderr)
