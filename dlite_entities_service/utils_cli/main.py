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
from rich import print  # pylint: disable=redefined-builtin
from rich.console import Console

from dlite_entities_service import __version__
from dlite_entities_service.service.backend import ENTITIES_COLLECTION
from dlite_entities_service.utils_cli.config import APP as config_APP

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


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
            "[bold red]Error[/bold red]: Either a --file/-f or --dir/-d must be given."
        )
        raise typer.Exit(1)

    for directory in directories:
        for root, _, files in os.walk(directory):
            unique_filepaths |= set(
                Path(root) / file
                for file in files
                if file.lower().endswith(tuple(file_formats))
            )

    successes = []
    for filepath in unique_filepaths:
        if filepath.suffix[1:].lower() not in file_formats:
            ERROR_CONSOLE.print(
                "[bold yellow]Warning[/bold yellow]: File format "
                f"{filepath.suffix[1:].lower()!r} not supported. Skipping file: "
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
        except dlite.DLiteError as exc:  # pylint: disable=redefined-outer-name
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} cannot be loaded with DLite. "
                f"DLite exception: {exc}"
            )
            raise typer.Exit(1) from exc

        ENTITIES_COLLECTION.insert_one(entity)
        successes.append(filepath)

    print(f"Successfully uploaded {len(successes)} entities: {successes}")


@APP.command()
def update():
    """Update an existing DLite entity."""
    print("Not implemented yet")


@APP.command()
def delete():
    """Delete an existing DLite entity."""
    print("Not implemented yet")


@APP.command()
def get():
    """Get an existing DLite entity."""
    print("Not implemented yet")


@APP.command()
def search():
    """Search for DLite entities."""
    print("Not implemented yet")


@APP.command()
def validate():
    """Validate a DLite entity."""
    print("Not implemented yet")
