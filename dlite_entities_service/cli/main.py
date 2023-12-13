"""Typer CLI for doing DLite entities service stuff."""
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
except ImportError as exc:  # pragma: no cover
    from dlite_entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

try:
    import dlite
except ImportError as exc:  # pragma: no cover
    if sys.version_info >= (3, 12):
        raise NotImplementedError(
            "Python 3.12 and newer is not yet supported. Please use Python 3.10 or "
            "3.11."
        ) from exc

    from dlite_entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

import yaml
from dotenv import dotenv_values, find_dotenv

from dlite_entities_service.cli._utils.generics import ERROR_CONSOLE, print
from dlite_entities_service.cli._utils.global_settings import global_options
from dlite_entities_service.cli.config import APP as config_APP
from dlite_entities_service.service.backend import (
    ENTITIES_COLLECTION,
    AnyWriteError,
    get_collection,
)

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from pymongo.collection import Collection


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

        # Turn all keys to uppercase
        config = {key.upper(): value for key, value in config.items()}

        backend_options = {
            "uri": config.get("ENTITY_SERVICE_MONGO_URI"),
            "username": config.get("ENTITY_SERVICE_MONGO_USER"),
            "password": config.get("ENTITY_SERVICE_MONGO_PASSWORD"),
        }

        if any(_ is not None for _ in backend_options.values()):
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
        [EntityFileFormats.JSON.value],
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
        except (
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
        except AnyWriteError as exc:  # pragma: no cover
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