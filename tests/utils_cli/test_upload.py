"""Tests for `entities-service upload` CLI command."""
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from typer.testing import CliRunner


def test_upload_no_args(cli: "CliRunner") -> None:
    """Test `entities-service upload` CLI command."""
    from dlite_entities_service.utils_cli.main import APP, upload

    result = cli.invoke(APP, "upload")
    assert result.exit_code == 0
    assert upload.__doc__ in result.stdout

    assert result.stdout == cli.invoke(APP, "upload --help").stdout


def test_upload_filepath(
    cli: "CliRunner", samples: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test upload with a filepath."""
    import json

    from mongomock import MongoClient

    from dlite_entities_service.service.config import CONFIG
    from dlite_entities_service.utils_cli import main

    mongo_client = MongoClient(CONFIG.mongo_uri)
    mock_entities_collection = mongo_client["dlite"]["entities"]

    monkeypatch.setattr(main, "ENTITIES_COLLECTION", mock_entities_collection)
    monkeypatch.setattr(
        main, "get_collection", lambda *args, **kwargs: mock_entities_collection
    )

    result = cli.invoke(
        main.APP, f"upload --file {samples / 'valid_entities' / 'Person.json'}"
    )
    assert result.exit_code == 0

    assert mock_entities_collection.count_documents({}) == 1
    stored_entity: "dict[str, Any]" = mock_entities_collection.find_one({})
    stored_entity.pop("_id")
    assert stored_entity == json.loads(
        (samples / "valid_entities" / "Person.json").read_bytes()
    )

    assert "Successfully uploaded 1 entities:" in result.stdout


def test_upload_filepath_invalid(cli: "CliRunner", samples: "Path") -> None:
    """Test upload with an invalid filepath."""
    from dlite_entities_service.utils_cli.main import APP

    result = cli.invoke(
        APP, f"upload --file {samples / 'invalid_entities' / 'Person.json'}"
    )
    assert result.exit_code == 1
    assert "cannot be loaded with DLite." in result.stderr
    assert not result.stdout


def test_upload_filepath_invalid_format(cli: "CliRunner", tmp_path: "Path") -> None:
    """Test upload with an invalid file format."""
    from dlite_entities_service.utils_cli.main import APP

    (tmp_path / "Person.txt").touch()

    result = cli.invoke(APP, f"upload --file {tmp_path / 'Person.txt'}")
    assert result.exit_code == 0
    assert "File format 'txt' is not supported." in result.stderr
    assert "No entities were uploaded." in result.stdout


def test_upload_no_file_or_dir(cli: "CliRunner") -> None:
    """Test error when no file or directory is provided."""
    from dlite_entities_service.utils_cli.main import APP

    result = cli.invoke(APP, "upload --format json")
    assert result.exit_code == 1
    assert "Missing either option '--file' / '-f'" in result.stderr
    assert not result.stdout


def test_upload_directory(
    cli: "CliRunner", samples: "Path", monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test upload with a directory."""
    import json

    from mongomock import MongoClient

    from dlite_entities_service.service.config import CONFIG
    from dlite_entities_service.utils_cli import main

    mongo_client = MongoClient(CONFIG.mongo_uri)
    mock_entities_collection = mongo_client["dlite"]["entities"]

    monkeypatch.setattr(main, "ENTITIES_COLLECTION", mock_entities_collection)
    monkeypatch.setattr(
        main, "get_collection", lambda *args, **kwargs: mock_entities_collection
    )

    result = cli.invoke(main.APP, f"upload --dir {samples / 'valid_entities'}")
    assert result.exit_code == 0

    assert mock_entities_collection.count_documents({}) == 3
    stored_entities = list(mock_entities_collection.find({}))
    for stored_entity in stored_entities:
        stored_entity.pop("_id")
    for sample_file in ("Person.json", "Dog.json", "Cat.json"):
        assert (
            json.loads((samples / "valid_entities" / sample_file).read_bytes())
            in stored_entities
        )

    assert "Successfully uploaded 3 entities:" in result.stdout
