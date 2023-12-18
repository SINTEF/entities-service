"""Tests for `entities-service upload` CLI command."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from pymongo.collection import Collection
    from typer.testing import CliRunner


def test_upload_no_args(cli: CliRunner) -> None:
    """Test `entities-service upload` CLI command."""
    from dlite_entities_service.cli.main import APP, upload

    result = cli.invoke(APP, "upload")
    assert result.exit_code == 0, result.stderr
    assert upload.__doc__ in result.stdout

    assert result.stdout == cli.invoke(APP, "upload --help").stdout


def test_upload_filepath(
    cli: CliRunner, static_dir: Path, mock_entities_collection: Collection
) -> None:
    """Test upload with a filepath."""
    import json

    from dlite_entities_service.cli import main

    result = cli.invoke(
        main.APP, f"upload --file {static_dir / 'valid_entities' / 'Person.json'}"
    )
    assert result.exit_code == 0, result.stderr

    assert mock_entities_collection.count_documents({}) == 1
    stored_entity: dict[str, Any] = mock_entities_collection.find_one({})
    stored_entity.pop("_id")
    assert stored_entity == json.loads(
        (static_dir / "valid_entities" / "Person.json").read_bytes()
    )

    assert "Successfully uploaded 1 entity:" in result.stdout


def test_upload_filepath_invalid(cli: CliRunner, static_dir: Path) -> None:
    """Test upload with an invalid filepath."""
    from dlite_entities_service.cli.main import APP

    result = cli.invoke(
        APP, f"upload --file {static_dir / 'invalid_entities' / 'Person.json'}"
    )
    assert result.exit_code == 1, result.stdout
    assert "Person.json is not a valid SOFT entity:" in result.stderr.replace("\n", "")
    assert "validation error for SOFT7Entity" in result.stderr.replace("\n", "")
    assert "validation errors for SOFT5Entity" in result.stderr.replace("\n", "")
    assert not result.stdout


def test_upload_filepath_invalid_format(cli: CliRunner, tmp_path: Path) -> None:
    """Test upload with an invalid file format."""
    from dlite_entities_service.cli.main import APP

    (tmp_path / "Person.txt").touch()

    result = cli.invoke(APP, f"upload --file {tmp_path / 'Person.txt'}")
    assert result.exit_code == 0, result.stderr
    assert "File format 'txt' is not supported." in result.stderr
    assert "No entities were uploaded." in result.stdout


def test_upload_no_file_or_dir(cli: CliRunner) -> None:
    """Test error when no file or directory is provided."""
    from dlite_entities_service.cli.main import APP

    result = cli.invoke(APP, "upload --format json")
    assert result.exit_code == 1, result.stdout
    assert "Missing either option '--file' / '-f'" in result.stderr
    assert not result.stdout


def test_upload_directory(
    cli: CliRunner, static_dir: Path, mock_entities_collection: Collection
) -> None:
    """Test upload with a directory."""
    import json

    from dlite_entities_service.cli import main

    directory = static_dir / "valid_entities"

    result = cli.invoke(main.APP, f"upload --dir {directory}")
    assert result.exit_code == 0, result.stderr

    original_entities = list(directory.glob("*.json"))

    assert mock_entities_collection.count_documents({}) == len(original_entities)

    stored_entities = list(mock_entities_collection.find({}))
    for stored_entity in stored_entities:
        # Remove MongoDB ID
        stored_entity.pop("_id")

    for sample_file in original_entities:
        # If the sample file contains a '$ref' key, it will be stored in the DB as 'ref'
        # instead. This is due to the fact that MongoDB does not allow keys to start
        # with a '$' character.
        parsed_sample_file: dict[str, Any] = json.loads(sample_file.read_bytes())
        if isinstance(parsed_sample_file["properties"], list):
            for index, property_value in enumerate(
                list(parsed_sample_file["properties"])
            ):
                if "$ref" in property_value:
                    property_value["ref"] = property_value.pop("$ref")
                    parsed_sample_file["properties"][index] = property_value
        else:
            # Expect "properties" to be a dict
            for property_name, property_value in list(
                parsed_sample_file["properties"].items()
            ):
                if "$ref" in property_value:
                    property_value["ref"] = property_value.pop("$ref")
                    parsed_sample_file["properties"][property_name] = property_value

        assert parsed_sample_file in stored_entities

    assert f"Successfully uploaded {len(original_entities)} entities:" in result.stdout


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
        assert result.exit_code == 1, result.stderr
        assert "Error: No files found with the given options." in result.stderr.replace(
            "│\n│ ", ""
        ), result.stderr
        assert not result.stdout


def test_get_backend(
    cli: CliRunner,
    dotenv_file: Path,
    static_dir: Path,
    mock_entities_collection: Collection,
) -> None:
    """Test that a found '.env' file is utilized."""
    import json

    from dotenv import set_key

    from dlite_entities_service.cli._utils.global_settings import CONTEXT
    from dlite_entities_service.cli.main import APP

    # Create a temporary '.env' file
    if not dotenv_file.exists():
        dotenv_file.touch()
    else:
        dotenv_file.unlink()
        dotenv_file.touch()
    set_key(dotenv_file, "ENTITY_SERVICE_MONGO_URI", "mongodb://localhost:27017")

    CONTEXT["dotenv_path"] = dotenv_file

    result = cli.invoke(
        APP, f"upload --file {static_dir / 'valid_entities' / 'Person.json'}"
    )
    assert result.exit_code == 0, result.stderr

    assert mock_entities_collection.count_documents({}) == 1
    stored_entity: dict[str, Any] = mock_entities_collection.find_one({})
    stored_entity.pop("_id")
    assert stored_entity == json.loads(
        (static_dir / "valid_entities" / "Person.json").read_bytes()
    )

    assert "Successfully uploaded 1 entity:" in result.stdout, result.stdout
