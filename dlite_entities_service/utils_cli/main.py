"""Typer CLI for doing DLite entities service stuff."""
# pylint: disable=duplicate-code
import json
import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

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

from dlite_entities_service import __version__
from dlite_entities_service.service.backend import (
    ENTITIES_COLLECTION,
    AnyWriteError,
    get_collection,
)
from dlite_entities_service.utils_cli.config import APP as config_APP

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from pymongo.collection import Collection


ERROR_CONSOLE = Console(stderr=True)


class EntityFileFormats(str, Enum):
    """Supported entity file formats."""

    JSON = "json"
    YAML = "yaml"
    YML = "yml"


APP = typer.Typer(
    name="entities-service",
    help="DLite entities service utility CLI",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
APP.add_typer(config_APP)


def _print_version(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"dlite-entities-service version: {__version__}")
        raise typer.Exit()


def _get_backend() -> "Collection":
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


@APP.callback()
def main(
    _: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit",
        is_eager=True,
        callback=_print_version,
    ),
) -> None:
    """DLite entities service utility CLI."""


@APP.command(no_args_is_help=True)
def upload(
    filepaths: Optional[list[Path]] = typer.Option(
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
    directories: Optional[list[Path]] = typer.Option(
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
            "format(s) in the directory will be uploaded. Subdirectories will be "
            "ignored."
        ),
        show_default=False,
    ),
    file_formats: Optional[list[EntityFileFormats]] = typer.Option(
        [EntityFileFormats.JSON],
        "--format",
        help="Format of DLite entity file.",
        show_choices=True,
        show_default=True,
        case_sensitive=False,
    ),
) -> None:
    """Upload a DLite entity."""
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
            unique_filepaths |= set(
                Path(root) / file
                for file in files
                if file.lower().endswith(tuple(file_formats))
            )

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

        entity: "dict[str, Any]" = (
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


@APP.command()
def iterate():
    """Iterate on an existing DLite entity.

    This means uploading a new version of an existing entity.
    """
    print("Not implemented yet")


@APP.command()
def update():
    """Update an existing DLite entity."""
    print("Not implemented yet")


@APP.command(no_args_is_help=True)
def delete(
    uri: str = typer.Argument(
        ...,
        help="URI of the DLite entity to delete.",
        show_default=False,
    ),
):
    """Delete an existing DLite entity."""
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
        ...,
        help="URI of the DLite entity to get.",
        show_default=False,
    ),
):
    """Get an existing DLite entity."""
    backend = _get_backend()

    if not backend.count_documents({"uri": uri}):
        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: No entity found with URI {uri!r}."
        )
        raise typer.Exit(1)

    entity_dict: "dict[str, Any]" = backend.find_one({"uri": uri})
    entity_dict.pop("_id")
    entity = dlite.Instance.from_dict(entity_dict, single=True, check_storages=False)
    print(entity)


@APP.command()
def search():
    """Search for DLite entities."""
    print("Not implemented yet")


@APP.command()
def validate():
    """Validate a DLite entity."""
    print("Not implemented yet")
