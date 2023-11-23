"""Typer CLI for doing DLite entities service stuff."""
# pylint: disable=duplicate-code
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Enum with string values."""


try:
    import typer
except ImportError as exc:
    raise ImportError(
        "Please install the DLite entities service utility CLI with "
        f"'pip install {Path(__file__).resolve().parent.parent.parent.resolve()}[cli]'"
    ) from exc

import dlite
import yaml
from dotenv import dotenv_values, find_dotenv
from rich import print  # pylint: disable=redefined-builtin
from rich.console import Console

from dlite_entities_service.service.backend import (
    ENTITIES_COLLECTION,
    AnyWriteError,
    get_collection,
)
from dlite_entities_service.utils_cli._utils.global_settings import global_options
from dlite_entities_service.utils_cli.config import APP as config_APP

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from pymongo.collection import Collection


ERROR_CONSOLE = Console(stderr=True)


class EntityFileFormats(StrEnum):
    """Supported entity file formats."""

    JSON = "json"
    YAML = "yaml"
    YML = "yml"


# Type Aliases
OptionalListEntityFileFormats = Optional[list[EntityFileFormats]]
OptionalListStr = Optional[list[str]]
OptionalListPath = Optional[list[Path]]
OptionalStr = Optional[str]


APP = typer.Typer(
    name="entities-service",
    help="DLite entities service utility CLI",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    callback=global_options,
)
APP.add_typer(config_APP, callback=global_options)


def _get_backend() -> Collection:
    """Return the backend."""
    config_file = find_dotenv()
    if config_file:
        config = dotenv_values(config_file)
        backend_options = {
            "uri": config.get("entity_service_mongo_uri"),
            "username": config.get("entity_service_mongo_user"),
            "password": config.get("entity_service_mongo_password"),
        }
        if all(_ is None for _ in backend_options.values()):
            return ENTITIES_COLLECTION
        return get_collection(**backend_options)
    return ENTITIES_COLLECTION


@APP.command(no_args_is_help=True)
def upload(
    filepaths: OptionalListPath = typer.Option(
        None,
        "--file",
        "-f",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to DLite entity file.",
        show_default=False,
    ),
    directories: OptionalListPath = typer.Option(
        None,
        "--dir",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help=(
            "Path to directory with DLite entities. All files matching the given "
            "format(s) in the directory will be uploaded. "
            "Subdirectories will be ignored."
        ),
        show_default=False,
    ),
    file_formats: OptionalListEntityFileFormats = typer.Option(
        [EntityFileFormats.JSON],
        "--format",
        help="Format of DLite entity file(s).",
        show_choices=True,
        show_default=True,
        case_sensitive=False,
    ),
) -> None:
    """Upload (local) DLite entities to a remote location."""
    unique_filepaths = set(filepaths or [])
    directories = list(set(directories or []))
    file_formats = list(set(file_formats or []))

    if not filepaths and not directories:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Missing either option '--file' / '-f' or "
            "'--dir' / '-d'."
        )
        raise typer.Exit(1)

    for directory in directories:
        for root, _, files in os.walk(directory):
            unique_filepaths |= {
                Path(root) / file
                for file in files
                if file.lower().endswith(tuple(file_formats))
            }

    if not unique_filepaths:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: No files found with the given options."
        )
        raise typer.Exit(1)

    successes = []
    for filepath in unique_filepaths:
        if filepath.suffix[1:].lower() not in file_formats:
            ERROR_CONSOLE.print(
                "[bold yellow]Warning[/bold yellow]: File format "
                f"{filepath.suffix[1:].lower()!r} is not supported. Skipping file: "
                f"{filepath}"
            )
            continue

        entity: dict[str, Any] = (
            json.loads(filepath.read_bytes())
            if filepath.suffix[1:].lower() == "json"
            else yaml.safe_load(filepath.read_bytes())
        )

        try:
            dlite.Instance.from_dict(entity, single=True, check_storages=False)
        except (  # pylint: disable=redefined-outer-name
            dlite.DLiteError,
            KeyError,
        ) as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} cannot be loaded with DLite. "
                f"DLite exception: {exc}"
            )
            raise typer.Exit(1) from exc

        try:
            _get_backend().insert_one(entity)
        except AnyWriteError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} cannot be uploaded. "
                f"Backend exception: {exc}"
            )
            raise typer.Exit(1) from exc

        successes.append(filepath)

    if successes:
        print(
            f"Successfully uploaded {len(successes)} entities: "
            f"{[str(_) for _ in successes]}"
        )
    else:
        print("No entities were uploaded.")


@APP.command(hidden=True)
def iterate() -> None:
    """Iterate on an existing DLite entity.

    This means uploading a new version of an existing entity.
    """
    print("Not implemented yet")


@APP.command(no_args_is_help=True)
def update(
    filepaths: OptionalListPath = typer.Option(
        None,
        "--file",
        "-f",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to DLite entity file.",
        show_default=False,
    ),
    directories: OptionalListPath = typer.Option(
        None,
        "--dir",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help=(
            "Path to directory with DLite entities. All files matching the given "
            "format(s) in the directory will be uploaded. "
            "Subdirectories will be ignored."
        ),
        show_default=False,
    ),
    file_formats: OptionalListEntityFileFormats = typer.Option(
        [EntityFileFormats.JSON],
        "--format",
        help="Format of DLite entity file(s).",
        show_choices=True,
        show_default=True,
        case_sensitive=False,
    ),
    insert: bool = typer.Option(
        False,
        "--insert",
        "-i",
        help="Insert the entity if it does not exist yet.",
        show_default=False,
        is_flag=True,
    ),
) -> None:
    """Update an existing (remote) DLite entity."""
    unique_filepaths = set(filepaths or [])
    directories = list(set(directories or []))
    file_formats = list(set(file_formats or []))

    if not filepaths and not directories:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Missing either option '--file' / '-f' or "
            "'--dir' / '-d'."
        )
        raise typer.Exit(1)

    for directory in directories:
        for root, _, files in os.walk(directory):
            unique_filepaths |= {
                Path(root) / file
                for file in files
                if file.lower().endswith(tuple(file_formats))
            }

    if not unique_filepaths:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: No files found with the given options."
        )
        raise typer.Exit(1)

    successes = []
    inserted = []
    for filepath in unique_filepaths:
        if filepath.suffix[1:].lower() not in file_formats:
            ERROR_CONSOLE.print(
                "[bold yellow]Warning[/bold yellow]: File format "
                f"{filepath.suffix[1:].lower()!r} is not supported. Skipping file: "
                f"{filepath}"
            )
            continue

        entity: dict[str, Any] = (
            json.loads(filepath.read_bytes())
            if filepath.suffix[1:].lower() == "json"
            else yaml.safe_load(filepath.read_bytes())
        )

        try:
            dlite.Instance.from_dict(entity, single=True, check_storages=False)
        except (  # pylint: disable=redefined-outer-name
            dlite.DLiteError,
            KeyError,
        ) as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} cannot be loaded with DLite. "
                f"DLite exception: {exc}"
            )
            raise typer.Exit(1) from exc

        try:
            result = _get_backend().update_one(
                filter={"uri": entity["uri"]},
                update=entity,
                upsert=insert,
            )
        except AnyWriteError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} cannot be uploaded. "
                f"Backend exception: {exc}"
            )
            raise typer.Exit(1) from exc

        if insert and result.upserted_id:
            inserted.append(filepath)

        successes.append(filepath)

    if successes and inserted:
        print(
            f"Successfully updated {len(successes) - len(inserted)} entities and "
            f"inserted {len(inserted)} new entities: "
            f"{[str(_) for _ in successes if _ not in inserted]} "
            f"and {[str(_) for _ in inserted]}"
        )
    elif successes:
        print(
            f"Successfully updated {len(successes)} entities: "
            f"{[str(_) for _ in successes]}"
        )
    else:
        print("No entities were updated.")


@APP.command(no_args_is_help=True)
def delete(
    uri: str = typer.Argument(
        help="URI of the DLite entity to delete.",
        show_default=False,
    ),
) -> None:
    """Delete an existing (remote) DLite entity."""
    backend = _get_backend()

    if not backend.count_documents({"uri": uri}):
        print(f"Already no entity found with URI {uri!r}.")
        raise typer.Exit()

    typer.confirm(
        f"Are you sure you want to delete entity with URI {uri!r}?", abort=True
    )

    backend.delete_one({"uri": uri})
    if backend.count_documents({"uri": uri}):
        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: Failed to delete entity with URI {uri!r}."
        )
        raise typer.Exit(1)
    print(f"Successfully deleted entity with URI {uri!r}.")


@APP.command(no_args_is_help=True)
def get(
    uri: str = typer.Argument(
        help="URI of the DLite entity to get.",
        show_default=False,
    ),
) -> None:
    """Get an existing (remote) DLite entity."""
    backend = _get_backend()

    if not backend.count_documents({"uri": uri}):
        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: No entity found with URI {uri!r}."
        )
        raise typer.Exit(1)

    entity_dict: dict[str, Any] = backend.find_one({"uri": uri})
    entity_dict.pop("_id")
    entity = dlite.Instance.from_dict(entity_dict, single=True, check_storages=False)
    print(entity)


@APP.command(no_args_is_help=True)
def search(
    uris: OptionalListStr = typer.Argument(
        None,
        metavar="[URI]...",
        help=(
            "URI of the DLite entity to search for. Multiple URIs can be provided. "
            "Note, the 'http://onto-ns.com/meta' prefix is optional."
        ),
        show_default=False,
    ),
    query: OptionalStr = typer.Option(
        None,
        "--query",
        "-q",
        help="Backend-specific query to search for DLite entities.",
        show_default=False,
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Return the search results as JSON.",
        show_default=False,
        is_flag=True,
    ),
) -> None:
    """Search for (remote) DLite entities."""
    backend = _get_backend()

    if not uris and not query:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Missing either argument 'URI' or option "
            "'query'."
        )
        raise typer.Exit(1)

    backend_query: dict[str, Any] | None = json.loads(query) if query else None
    if uris:
        uris = [
            uri
            if uri.startswith("http://onto-ns.com/meta")
            else f"http://onto-ns.com/meta/{uri.lstrip('/')}"
            for uri in uris
        ]
        backend_query = (
            {"$and": [{"uri": {"$in": uris}}, backend_query]}
            if backend_query
            else {"uri": {"$in": uris}}
        )

    if backend_query is None:
        ERROR_CONSOLE.print("[bold red]Error[/bold red]: Internal CLI error.")
        raise typer.Exit(1)

    found_entities: list[dlite.Instance] = []
    for raw_entity in backend.find(backend_query):
        raw_entity.pop("_id")
        entity: dlite.Instance = dlite.Instance.from_dict(
            raw_entity, single=True, check_storages=False
        )
        found_entities.append(entity)

    if as_json:
        print(json.dumps([_.asdict(uuid=False) for _ in found_entities]))
        raise typer.Exit()

    print(f"Found {len(found_entities)} entities: {[_.uuid for _ in found_entities]}")


@APP.command(no_args_is_help=True)
def validate(
    filepaths: OptionalListPath = typer.Option(
        None,
        "--file",
        "-f",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to DLite entity file.",
        show_default=False,
    ),
    directories: OptionalListPath = typer.Option(
        None,
        "--dir",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help=(
            "Path to directory with DLite entities. All files matching the given "
            "format(s) in the directory will be validated. "
            "Subdirectories will be ignored."
        ),
        show_default=False,
    ),
    file_formats: OptionalListEntityFileFormats = typer.Option(
        [EntityFileFormats.JSON],
        "--format",
        help="Format of DLite entity file(s).",
        show_choices=True,
        show_default=True,
        case_sensitive=False,
    ),
) -> None:
    """Validate (local) DLite entities."""
    unique_filepaths = set(filepaths or [])
    directories = list(set(directories or []))
    file_formats = list(set(file_formats or []))

    if not filepaths and not directories:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Missing either option '--file' / '-f' or "
            "'--dir' / '-d'."
        )
        raise typer.Exit(1)

    for directory in directories:
        for root, _, files in os.walk(directory):
            unique_filepaths |= {
                Path(root) / file
                for file in files
                if file.lower().endswith(tuple(file_formats))
            }

    if not unique_filepaths:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: No files found with the given options."
        )
        raise typer.Exit(1)

    for filepath in unique_filepaths:
        if filepath.suffix[1:].lower() not in file_formats:
            ERROR_CONSOLE.print(
                "[bold yellow]Warning[/bold yellow]: File format "
                f"{filepath.suffix[1:].lower()!r} is not supported. Skipping file: "
                f"{filepath}"
            )
            continue

        entity: dict[str, Any] = (
            json.loads(filepath.read_bytes())
            if filepath.suffix[1:].lower() == "json"
            else yaml.safe_load(filepath.read_bytes())
        )

        try:
            dlite.Instance.from_dict(entity, single=True, check_storages=False)
        except (  # pylint: disable=redefined-outer-name
            dlite.DLiteError,
            KeyError,
        ):
            print(f"{filepath} [bold red]invalid[/bold red]")
        else:
            print(f"{filepath} [bold green]valid[/bold green]")
