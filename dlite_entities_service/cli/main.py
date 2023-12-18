"""Typer CLI for doing SOFT entities service stuff."""
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


import yaml
from dotenv import dotenv_values
from pydantic import AnyHttpUrl

from dlite_entities_service.cli._utils.generics import (
    ERROR_CONSOLE,
    pretty_compare_dicts,
    print,
)
from dlite_entities_service.cli._utils.global_settings import CONTEXT, global_options
from dlite_entities_service.cli.config import APP as config_APP
from dlite_entities_service.models import (
    URI_REGEX,
    get_updated_version,
    get_uri,
    get_version,
    soft_entity,
)
from dlite_entities_service.service.exceptions import BackendError

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
    help="SOFT entities service utility CLI",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    callback=global_options,
)
APP.add_typer(config_APP, callback=global_options)


def _get_backend() -> Collection:
    """Return the backend."""
    from dlite_entities_service.service.backend import (
        ENTITIES_COLLECTION,
        get_collection,
    )

    config_file = CONTEXT["dotenv_path"]

    if config_file.exists():
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
        help="Path to entity file.",
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
            "Path to directory with entities. All files matching the given "
            "format(s) in the directory will be uploaded. "
            "Subdirectories will be ignored. Can be provided multiple times."
        ),
        show_default=False,
    ),
    file_formats: OptionalListEntityFileFormats = typer.Option(
        [EntityFileFormats.JSON.value],
        "--format",
        help="Format of entity file(s).",
        show_choices=True,
        show_default=True,
        case_sensitive=False,
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast",
        help="Stop uploading entities on the first error during file validation.",
        show_default=True,
    ),
) -> None:
    """Upload (local) entities to a remote location."""
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

    successes: list[tuple[Path, dict[str, Any]]] = []
    skipped: list[Path] = []
    failed: list[Path] = []

    informed_file_formats: set[str] = set()
    for filepath in unique_filepaths:
        if (file_format := filepath.suffix[1:].lower()) not in file_formats:
            print(f"[bold blue]Info[/bold blue]: Skipping file: {filepath}")

            # The rest of the code in this block is to ensure we only print extra info
            # or warning messages the first time a new file format is encountered.
            if file_format in informed_file_formats:
                skipped.append(filepath)
                continue

            if file_format in EntityFileFormats.__members__.values():
                print(
                    f"[bold blue]Info[/bold blue]: File format {file_format!r} can be "
                    f"uploaded by adding the option: --format={file_format}"
                )
            else:
                ERROR_CONSOLE.print(
                    f"[bold yellow]Warning[/bold yellow]: File format {file_format!r} "
                    "is not supported."
                )

            informed_file_formats.add(file_format)
            skipped.append(filepath)
            continue

        entity: dict[str, Any] = (
            json.loads(filepath.read_bytes())
            if file_format == "json"
            else yaml.safe_load(filepath.read_bytes())
        )

        # Validate entity
        entity_model_or_errors = soft_entity(return_errors=True, **entity)
        if isinstance(entity_model_or_errors, list):
            error_list = "\n\n".join(str(error) for error in entity_model_or_errors)
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} is not a valid SOFT entity:"
                f"\n\n{error_list}\n"
            )
            if fail_fast:
                raise typer.Exit(1)
            failed.append(filepath)
            continue

        backend = _get_backend()

        # Check if entity already exists
        if TYPE_CHECKING:  # pragma: no cover
            existing_entity: dict[str, Any]

        if (
            existing_entity := backend.find_one(
                {"uri": get_uri(entity_model_or_errors)}
            )
        ) is not None:
            # Compare existing model with new model

            # Prepare entities: Remove _id from existing entity and dump new entity
            # from model
            existing_entity.pop("_id", None)
            dumped_entity = entity_model_or_errors.model_dump()

            if existing_entity == dumped_entity:
                print(
                    "[bold blue]Info[/bold blue]: Entity already exists in the "
                    f"database. Skipping file: {filepath}"
                )
                skipped.append(filepath)
                continue

            print(
                "[bold blue]Info[/bold blue]: Entity already exists in the "
                "database, but they differ in their content.\nDifference between "
                f"existing entity (first) and incoming entity (second) {filepath}:\n\n"
                + pretty_compare_dicts(existing_entity, dumped_entity)
            )

            try:
                update_version = typer.confirm(
                    "You cannot overwrite existing entities. Do you wish to upload the "
                    "new entity with an updated version?",
                    default=True,
                )
            except typer.Abort:
                update_version = False

            if not update_version:
                print(f"[bold blue]Info[/bold blue]: Skipping file: {filepath}")
                skipped.append(filepath)
                continue

            # Passing incoming entity-as-model here, since the URIs (and thereby the
            # versions) have already been determined to be the same, and the function
            # only accepts models.
            try:
                new_version: str = typer.prompt(
                    "The existing entity's version is "
                    f"{get_version(entity_model_or_errors)!r}. Please enter the new "
                    "version:",
                    default=get_updated_version(entity_model_or_errors),
                    abort=False,
                    type=str,
                    confirmation_prompt=True,
                )
            except typer.Abort:
                print(f"[bold blue]Info[/bold blue]: Skipping file: {filepath}")
                skipped.append(filepath)
                continue

            if entity_model_or_errors.version is not None:
                entity_model_or_errors.version = new_version
                entity_model_or_errors.uri = AnyHttpUrl(
                    f"{entity_model_or_errors.namespace}/{new_version}"
                    f"/{entity_model_or_errors.name}"
                )
            else:
                if (match := URI_REGEX.match(str(entity_model_or_errors.uri))) is None:
                    ERROR_CONSOLE.print(
                        f"[bold red]Error[/bold red]: Cannot parse URI to get version: "
                        f"{entity_model_or_errors.uri}"
                    )
                    if fail_fast:
                        raise typer.Exit(1)
                    failed.append(filepath)
                    continue

                entity_model_or_errors.uri = AnyHttpUrl(
                    f"{match.group('namespace')}/{new_version}/{match.group('name')}"
                )

        # Prepare entity for upload
        # Specifically, rename '$ref' keys to 'ref'
        dumped_entity = entity_model_or_errors.model_dump(
            by_alias=True, mode="json", exclude_unset=True
        )

        # SOFT5
        if isinstance(dumped_entity["properties"], list):
            dumped_entity["properties"] = [
                {key.replace("$ref", "ref"): value for key, value in prop.items()}
                for prop in dumped_entity["properties"]
            ]

        # SOFT7
        else:
            for property_name, property_value in list(
                dumped_entity["properties"].items()
            ):
                dumped_entity["properties"][property_name] = {
                    key.replace("$ref", "ref"): value
                    for key, value in property_value.items()
                }

        successes.append((filepath, dumped_entity))

    # Exit if errors occurred
    if failed:
        ERROR_CONSOLE.print(
            f"[bold red]Failed to upload {len(failed)} "
            f"entit{'y' if len(failed) == 1 else 'ies'}, see above for more "
            "details:[/bold red]\n"
            + "\n".join([str(entity_filepath) for entity_filepath in failed])
        )
        raise typer.Exit(1)

    # Upload entities
    if successes:
        try:
            backend.insert_many([entity for _, entity in successes])
        except BackendError as exc:  # pragma: no cover
            ERROR_CONSOLE.print(
                "[bold red]Error[/bold red]: Could not upload "
                f"entit{'y' if len(successes) == 1 else 'ies'}. "
                f"Backend exception: {exc}"
            )
            raise typer.Exit(1) from exc

        print(
            f"[bold green]Successfully uploaded {len(successes)} "
            f"entit{'y' if len(successes) == 1 else 'ies'}:[/bold green]\n"
            + "\n".join([str(entity_filepath) for entity_filepath, _ in successes])
        )
    else:
        print("[bold blue]No entities were uploaded.[/bold blue]")

    if skipped:
        print(
            f"\n[bold yellow]Skipped {len(skipped)} "
            f"entit{'y' if len(skipped) == 1 else 'ies'}:[/bold yellow]\n"
            + "\n".join([str(entity_filepath) for entity_filepath in skipped])
        )
