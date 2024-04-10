"""Typer CLI for doing Entities Service stuff."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Optional

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Enum with string values."""


try:
    import httpx
    import typer
    from rich import box
    from rich.rule import Rule
    from rich.table import Table
except ImportError as exc:  # pragma: no cover
    from entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

import yaml
from pydantic import AnyHttpUrl

from entities_service.cli._utils.generics import (
    ERROR_CONSOLE,
    AuthenticationError,
    oauth,
    pretty_compare_dicts,
    print,
)
from entities_service.cli._utils.global_settings import global_options
from entities_service.cli.config import APP as config_APP
from entities_service.models import (
    URI_REGEX,
    Entity,
    get_updated_version,
    get_uri,
    get_version,
    soft_entity,
)
from entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


class ValidEntity(NamedTuple):
    """A tuple containing a valid entity along with relevant information.

    `None` values mean "unknown" or "not applicable".
    """

    entity: Entity
    exists_remotely: bool | None
    equal_to_remote: bool | None
    pretty_diff: str | None


class EntityFileFormats(StrEnum):
    """Supported entity file formats."""

    JSON = "json"
    YAML = "yaml"
    YML = "yml"


class StrReversor(str):
    """Utility class to reverse the comparison of strings.

    Can be used to sort individual string parts of an interable in reverse order.

    Adapted from: https://stackoverflow.com/a/56842689/12404091
    """

    def __init__(self, obj: str) -> None:
        self.obj = obj

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, StrReversor):
            return NotImplemented

        return value.obj == self.obj

    def __lt__(self, value: object, /) -> bool:
        if not isinstance(value, StrReversor):
            return NotImplemented

        return value.obj < self.obj


def _get_namespace_name_version(entity: Entity) -> tuple[str, str, str]:
    """Extract the namespace, name, and version from an entity.

    The version is reversed to sort it in descending order (utilizing StrReversor).
    """
    uri = get_uri(entity)

    if (matched_uri := URI_REGEX.match(uri)) is None:
        raise ValueError(
            f"Could not parse URI {uri} with regular expression " f"{URI_REGEX.pattern}"
        )

    return (
        matched_uri.group("specific_namespace") or "/",
        matched_uri.group("name"),
        StrReversor(matched_uri.group("version")),
    )


# Type Aliases
OptionalListEntityFileFormats = Optional[list[EntityFileFormats]]
OptionalListStr = Optional[list[str]]
OptionalListPath = Optional[list[Path]]
OptionalStr = Optional[str]


APP = typer.Typer(
    name="entities-service",
    help="Entities Service utility CLI",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    callback=global_options,
)
APP.add_typer(config_APP, callback=global_options)


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
        help="Path to file with one or more entities.",
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
            "Path to directory with files that include one or more entities. "
            "All files matching the given format(s) in the directory will be uploaded. "
            "Subdirectories will be ignored. This option can be provided multiple "
            "times, e.g., to include multiple subdirectories."
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
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "--silent",
        "-q",
        "-s",
        "-y",
        help=(
            "Do not print anything on success and do not ask for confirmation. "
            "IMPORTANT, for content conflicts the defaults will be chosen."
        ),
        show_default=True,
    ),
) -> None:
    """Upload (local) entities to a remote location."""
    unique_filepaths = set(filepaths or [])
    directories = list(set(directories or []))
    file_formats = list(set(file_formats or []))

    # Handle YAML/YML file format
    if EntityFileFormats.YAML in file_formats or EntityFileFormats.YML in file_formats:
        # Ensure both YAML and YML are in the list
        if EntityFileFormats.YAML not in file_formats:
            file_formats.append(EntityFileFormats.YAML)
        if EntityFileFormats.YML not in file_formats:
            file_formats.append(EntityFileFormats.YML)

    # Ensure the user is logged in
    login(quiet=True)

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

    unique_entity_uris: set[str] = set()
    unique_entities: list[Entity] = []

    informed_file_formats: set[str] = set()
    for filepath in unique_filepaths:
        if (file_format := filepath.suffix[1:].lower()) not in file_formats:
            if not quiet:
                print(f"[bold blue]Info[/bold blue]: Skipping file: {filepath}")

            # The rest of the code in this block is to ensure we only print extra info
            # or warning messages the first time a new file format is encountered.
            if file_format in informed_file_formats:
                skipped.append(filepath)
                continue

            if file_format in EntityFileFormats.__members__.values() and not quiet:
                print(
                    "[bold blue]Info[/bold blue]: Entities using the file format "
                    f"{file_format!r} can be uploaded by adding the option: "
                    f"--format={file_format}"
                )
            else:
                ERROR_CONSOLE.print(
                    f"[bold yellow]Warning[/bold yellow]: File format {file_format!r} "
                    "is not supported."
                )

            informed_file_formats.add(file_format)
            skipped.append(filepath)
            continue

        entities: list[dict[str, Any]] | dict[str, Any] = (
            json.loads(filepath.read_bytes())
            if file_format == "json"
            else yaml.safe_load(filepath.read_bytes())
        )

        if isinstance(entities, dict):
            entities = [entities]

        if not isinstance(entities, list) or not all(
            isinstance(entity, dict) for entity in entities
        ):
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {filepath} can not be read as either a "
                "single or a list of SOFT entities."
            )
            if fail_fast:
                raise typer.Exit(1)
            failed.append(filepath)
            continue

        for entity in entities:
            # Validate entity
            entity_model_or_errors = soft_entity(return_errors=True, **entity)
            if isinstance(entity_model_or_errors, list):
                # Error(s) occurred !
                error_list = "\n\n".join(str(error) for error in entity_model_or_errors)
                ERROR_CONSOLE.print(
                    f"[bold red]Error[/bold red]: {filepath} is not a valid SOFT "
                    f"entity:\n\n{error_list}\n"
                )
                if fail_fast:
                    raise typer.Exit(1)
                failed.append(filepath)
                continue

            # Check for duplicate URIs
            if (uri := get_uri(entity_model_or_errors)) in unique_entity_uris:
                ERROR_CONSOLE.print(
                    f"[bold red]Error[/bold red]: Duplicate URI found: {uri}"
                )
                if fail_fast:
                    raise typer.Exit(1)
                failed.append(filepath)
                continue

            unique_entity_uris.add(uri)
            unique_entities.append(entity_model_or_errors)

    # Evaluate each unique entity
    for entity_model in unique_entities:
        # Check if entity already exists
        with httpx.Client(follow_redirects=True) as client:
            try:
                response = client.get(get_uri(entity_model))
            except httpx.HTTPError as exc:
                ERROR_CONSOLE.print(
                    "[bold red]Error[/bold red]: Could not check if entity already "
                    f"exists. HTTP exception: {exc}"
                )
                raise typer.Exit(1) from exc

        existing_entity: dict[str, Any] | None = None
        if response.is_success:
            try:
                existing_entity = response.json()
            except json.JSONDecodeError as exc:
                ERROR_CONSOLE.print(
                    "[bold red]Error[/bold red]: Could not check if entity already "
                    f"exists. JSON decode error: {exc}"
                )
                raise typer.Exit(1) from exc

        if existing_entity is not None:
            # Compare existing model with new model

            # Prepare entities: Dump new entity from model
            dumped_entity = entity_model.model_dump(
                by_alias=True, mode="json", exclude_unset=True
            )

            if existing_entity == dumped_entity:
                if not quiet:
                    print(
                        "[bold blue]Info[/bold blue]: Entity already exists in the "
                        f"database. Skipping file: {filepath}"
                    )
                skipped.append(filepath)
                continue

            if not quiet:
                print(
                    "[bold blue]Info[/bold blue]: Entity already exists in the "
                    "database, but they differ in their content.\nDifference between "
                    f"existing entity (first) and incoming entity (second) {filepath}:"
                    f"\n\n{pretty_compare_dicts(existing_entity, dumped_entity)}\n"
                )

            if not quiet:
                try:
                    update_version = typer.confirm(
                        "You cannot overwrite existing entities. Do you wish to upload "
                        "the new entity with an updated version number?",
                        default=True,
                    )
                except typer.Abort:  # pragma: no cover
                    # Can only happen if the user presses Ctrl-C, which can not be
                    # tested currently
                    update_version = False
            else:
                # Use default
                update_version = True

            if not update_version:
                if not quiet:
                    print(f"[bold blue]Info[/bold blue]: Skipping file: {filepath}")
                skipped.append(filepath)
                continue

            if not quiet:
                # Passing incoming entity-as-model here, since the URIs (and thereby the
                # versions) have already been determined to be the same, and the
                # function only accepts models.
                try:
                    new_version: str = typer.prompt(
                        "The existing entity's version is "
                        f"{get_version(entity_model)!r}. Please enter the new "
                        "version",
                        default=get_updated_version(entity_model),
                        type=str,
                    )
                except typer.Abort:  # pragma: no cover
                    # Can only happen if the user presses Ctrl-C, which can not be
                    # tested currently
                    if not quiet:
                        print(f"[bold blue]Info[/bold blue]: Skipping file: {filepath}")
                    skipped.append(filepath)
                    continue
            else:
                # Use default
                new_version = get_updated_version(entity_model)

            # Validate new version
            error_message = ""
            if new_version == get_version(entity_model):
                error_message = (
                    "[bold red]Error[/bold red]: Could not update entity. "
                    f"New version ({new_version}) is the same as the existing version "
                    f"({get_version(entity_model)})."
                )
            elif re.match(r"^\d+(?:\.\d+){0,2}$", new_version) is None:
                error_message = (
                    "[bold red]Error[/bold red]: Could not update entity. "
                    f"New version ({new_version}) is not a valid SOFT version."
                )

            if error_message:
                ERROR_CONSOLE.print(error_message)
                if fail_fast:
                    raise typer.Exit(1)
                failed.append(filepath)
                continue

            # Update version and URI
            if entity_model.version is not None:
                entity_model.version = new_version
                entity_model.uri = AnyHttpUrl(
                    f"{entity_model.namespace}/{new_version}" f"/{entity_model.name}"
                )

            if entity_model.uri is not None:
                match = URI_REGEX.match(str(entity_model.uri))

                # match will always be a match object, since the URI has already been
                # validated by the model
                if TYPE_CHECKING:  # pragma: no cover
                    assert match is not None  # nosec

                entity_model.uri = AnyHttpUrl(
                    f"{match.group('namespace')}/{new_version}/{match.group('name')}"
                )

        # Prepare entity for upload
        # Specifically, rename '$ref' keys to 'ref'
        dumped_entity = entity_model.model_dump(
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

    if successes:
        if not quiet:
            # Have the user confirm the list of entities to upload
            table = Table(
                title="Entities to upload:",
                title_style="bold",
                title_justify="left",
                box=box.SIMPLE_HEAD,
                highlight=True,
            )

            table.add_column("Namespace", no_wrap=True)
            table.add_column("Entity", no_wrap=True)

            for _, entity in successes:
                if all(key in entity for key in ("namespace", "version", "name")):
                    namespace = (
                        entity["namespace"][len(str(CONFIG.base_url).rstrip("/")) :]
                        or "/"
                    )
                    version = entity["version"]
                    name = entity["name"]
                else:
                    # Use the uri/identity
                    matched_uri = URI_REGEX.match(entity["uri"])
                    if matched_uri is None:
                        raise ValueError(
                            f"Could not parse URI {entity['uri']} with regular "
                            f"expression {URI_REGEX.pattern}"
                        )
                    namespace = matched_uri.group("specific_namespace") or "/"
                    version = matched_uri.group("version")
                    name = matched_uri.group("name")

                table.add_row(namespace, f"{name} (ver. {version})")

            print("", table)

            try:
                upload_entities = typer.confirm(
                    "These entities will be uploaded. Do you want to continue?",
                    default=True,
                )
            except typer.Abort as exc:  # pragma: no cover
                # Can only happen if the user presses Ctrl-C, which can not be tested
                # currently
                # Take an Abort as a "no"
                print("[bold blue]Aborted: No entities were uploaded.[/bold blue]")
                raise typer.Exit() from exc

            if not upload_entities:
                print("[bold blue]No entities were uploaded.[/bold blue]")
                raise typer.Exit()

        # Upload entities
        with httpx.Client(base_url=str(CONFIG.base_url), auth=oauth) as client:
            try:
                response = client.post(
                    "/_admin/create", json=[entity for _, entity in successes]
                )
            except httpx.HTTPError as exc:
                ERROR_CONSOLE.print(
                    "[bold red]Error[/bold red]: Could not upload "
                    f"entit{'y' if len(successes) == 1 else 'ies'}. "
                    f"HTTP exception: {exc}"
                )
                raise typer.Exit(1) from exc

        if not response.is_success:
            try:
                error_message = response.json()
            except json.JSONDecodeError as exc:
                ERROR_CONSOLE.print(
                    "[bold red]Error[/bold red]: Could not upload "
                    f"entit{'y' if len(successes) == 1 else 'ies'}. "
                    f"JSON decode error: {exc}"
                )
                raise typer.Exit(1) from exc

            ERROR_CONSOLE.print(
                "[bold red]Error[/bold red]: Could not upload "
                f"entit{'y' if len(successes) == 1 else 'ies'}. "
                f"HTTP status code: {response.status_code}. "
                f"Error message: {error_message}"
            )
            raise typer.Exit(1)

        if not quiet:
            print(
                f"[bold green]Successfully uploaded {len(successes)} "
                f"entit{'y' if len(successes) == 1 else 'ies'}:[/bold green]\n"
                + "\n".join([str(entity_filepath) for entity_filepath, _ in successes])
            )
    elif not quiet:
        print("[bold blue]No entities were uploaded.[/bold blue]")

    if skipped and not quiet:
        print(
            f"\n[bold yellow]Skipped {len(skipped)} "
            f"entit{'y' if len(skipped) == 1 else 'ies'}:[/bold yellow]\n"
            + "\n".join([str(entity_filepath) for entity_filepath in skipped])
        )


@APP.command()
def login(
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "--silent",
        "-q",
        "-s",
        "-y",
        help="Do not print anything on success and do not ask for confirmation.",
        show_default=True,
    ),
) -> None:
    """Login to the entities service."""
    with httpx.Client(base_url=str(CONFIG.base_url)) as client:
        try:
            response = client.post("/_admin/create", json=[], auth=oauth)
        except httpx.HTTPError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not login. HTTP exception: {exc}"
            )
            raise typer.Exit(1) from exc
        except AuthenticationError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not login. Authentication failed "
                f"({exc.__class__.__name__}): {exc}"
            )
            raise typer.Exit(1) from exc
        except json.JSONDecodeError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not login. JSON decode error: {exc}"
            )
            raise typer.Exit(1) from exc

    if not response.is_success:
        try:
            error_message = response.json()
        except json.JSONDecodeError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not login. JSON decode error: {exc}"
            )
            raise typer.Exit(1) from exc

        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: Could not login. HTTP status code: "
            f"{response.status_code}. Error response: "
        )
        ERROR_CONSOLE.print_json(data=error_message)
        raise typer.Exit(1)

    if not quiet:
        print("[bold green]Successfully logged in.[/bold green]")


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
        help="Path to file with one or more entities.",
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
            "Path to directory with files that include one or more entities. "
            "All files matching the given format(s) in the directory will be validated."
            " Subdirectories will be ignored. This option can be provided multiple "
            "times, e.g., to include multiple subdirectories."
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
        help="Stop validating entities on the first discovered error.",
        show_default=True,
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "--silent",
        "-q",
        "-s",
        "-y",
        help="Do not print anything on success.",
        show_default=True,
    ),
    no_external_calls: bool = typer.Option(
        False,
        "--no-external-calls",
        help=(
            "Do not make any external calls to validate the entity/-ies. "
            "This includes comparing the local entity with the remote entity."
        ),
        show_default=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print the differences between the external and local entities (if any).",
        show_default=True,
    ),
) -> list[Entity]:
    """Validate (local) entities."""
    unique_filepaths = set(filepaths or [])
    directories = list(set(directories or []))
    file_formats = list(set(file_formats or []))

    # Handle YAML/YML file format
    if EntityFileFormats.YAML in file_formats or EntityFileFormats.YML in file_formats:
        # Ensure both YAML and YML are in the list
        if EntityFileFormats.YAML not in file_formats:
            file_formats.append(EntityFileFormats.YAML)
        if EntityFileFormats.YML not in file_formats:
            file_formats.append(EntityFileFormats.YML)

    if not filepaths and not directories:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Missing either option '--file' / '-f' or "
            "'--dir' / '-d'."
        )
        raise typer.Exit(1)

    ## Consolidate provided directories and filepaths

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

    successes: list[ValidEntity] = []
    failed_filepaths: list[Path] = []
    failed_entities: list[str] = []  # Failed entities' URI

    unique_entity_uris: set[str] = set()
    unique_entities: list[Entity] = []

    informed_file_formats: set[str] = set()

    ## Extract and validate each local entity

    for filepath in unique_filepaths:
        # Variable to use when printing the file path to the console
        repr_filepath = (
            ("./" + str(filepath.relative_to(Path.cwd())))
            if filepath.is_relative_to(Path.cwd())
            else filepath
        )

        if (file_format := filepath.suffix[1:].lower()) not in file_formats:
            if not quiet:
                print(f"[bold blue]Info[/bold blue]: Skipping file: {repr_filepath}")

            # The rest of the code in this block is to ensure we only print extra info
            # or warning messages the first time a new file format is encountered.
            if file_format in informed_file_formats:
                continue

            if file_format in EntityFileFormats.__members__.values() and not quiet:
                print(
                    "[bold blue]Info[/bold blue]: Entities using the file format "
                    f"{file_format!r} can be uploaded by adding the option: "
                    f"--format={file_format}"
                )
            else:
                ERROR_CONSOLE.print(
                    f"[bold yellow]Warning[/bold yellow]: File format {file_format!r} "
                    "is not supported."
                )

            informed_file_formats.add(file_format)
            continue

        entities: list[dict[str, Any]] | dict[str, Any] = (
            json.loads(filepath.read_bytes())
            if file_format == "json"
            else yaml.safe_load(filepath.read_bytes())
        )

        if isinstance(entities, dict):
            entities = [entities]

        if not isinstance(entities, list) or not all(
            isinstance(entity, dict) for entity in entities
        ):
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: {repr_filepath} can not be read as either"
                " a single or a list of SOFT entities."
            )
            if fail_fast:
                raise typer.Exit(1)
            failed_filepaths.append(filepath)
            continue

        for entity in entities:
            # Validate entity
            entity_model_or_errors = soft_entity(return_errors=True, **entity)
            if isinstance(entity_model_or_errors, list):
                # Error(s) occurred !
                error_list = "\n\n".join(str(error) for error in entity_model_or_errors)
                ERROR_CONSOLE.print(
                    f"[bold red]Error[/bold red]: {repr_filepath} contains an invalid "
                    f"SOFT entity:\n\n{error_list}\n"
                )
                if fail_fast:
                    raise typer.Exit(1)
                failed_filepaths.append(filepath)
                continue

            # Check for duplicate URIs
            if (uri := get_uri(entity_model_or_errors)) in unique_entity_uris:
                ERROR_CONSOLE.print(
                    f"[bold red]Error[/bold red]: Duplicate URI found: {uri}"
                )
                if fail_fast:
                    raise typer.Exit(1)
                failed_filepaths.append(filepath)
                failed_entities.append(uri)
                continue

            unique_entity_uris.add(uri)
            unique_entities.append(entity_model_or_errors)

    ## Evaluate each unique entity against its external/remote counter-part

    for entity_model in unique_entities:
        # Abort for-loop if `--no-external-calls` is provided
        if no_external_calls:
            if not quiet:
                print(
                    "[bold blue]Info[/bold blue]: No external calls will be made to "
                    "validate the entities."
                )
            successes = [
                ValidEntity(entity, None, None, None) for entity in unique_entities
            ]
            break

        # Check if entity exists at its given URL URI
        with httpx.Client(follow_redirects=True) as client:
            try:
                response = client.get(get_uri(entity_model))
            except httpx.HTTPError as exc:
                ERROR_CONSOLE.print(
                    "[bold red]Error[/bold red]: Could not check if entity already "
                    f"exists. HTTP exception: {exc}"
                )
                raise typer.Exit(1) from exc

        external_entity: dict[str, Any] | None = None
        if response.is_success:
            try:
                external_entity = response.json()
            except json.JSONDecodeError as exc:
                ERROR_CONSOLE.print(
                    "[bold red]Error[/bold red]: Could not check if entity already "
                    f"exists. JSON decode error: {exc}"
                )
                raise typer.Exit(1) from exc

        if external_entity is None:
            # Entity does not exist externally/remotely
            successes.append(ValidEntity(entity_model, False, None, None))
            continue

        ## Compare external/remote model with local model

        # Dump local entity to match the format of the external entity
        dumped_entity = entity_model.model_dump(
            by_alias=True, mode="json", exclude_unset=True
        )

        if external_entity == dumped_entity:
            successes.append(ValidEntity(entity_model, True, True, None))
        else:
            # Record the differences between the external and local entities
            successes.append(
                ValidEntity(
                    entity_model,
                    True,
                    False,
                    pretty_compare_dicts(external_entity, dumped_entity),
                )
            )

    ## Report the results

    # Errors occurred
    if failed_filepaths or failed_entities:
        ERROR_CONSOLE.print(
            "[bold red]Failed to validate one or more entities. "
            "See above for more details.[/bold red]\n"
        )

        if failed_filepaths:
            ERROR_CONSOLE.print(
                "[bold red]Files:[/bold red]\n  "
                + "\n  ".join(
                    [
                        (
                            ("./" + str(entity_filepath.relative_to(Path.cwd())))
                            if entity_filepath.is_relative_to(Path.cwd())
                            else str(entity_filepath)
                        )
                        for entity_filepath in failed_filepaths
                    ]
                )
                + ("\n" if failed_entities else "")
            )

        if failed_entities:
            ERROR_CONSOLE.print(
                "[bold red]Entities:[/bold red]\n  " + "\n  ".join(failed_entities)
            )

    if quiet:
        # No need to go further here, just return (or raise if errors) already
        if not (failed_filepaths or failed_entities):
            return [valid_entity.entity for valid_entity in successes]

        raise typer.Exit(1)

    # Report on validation successes
    if successes:
        # List the validated entities in a table
        table = Table(
            expand=True,
            box=box.HORIZONTALS,
            show_edge=False,
            highlight=True,
        )

        table.add_column("Namespace", no_wrap=True)
        table.add_column("Name", no_wrap=True)
        table.add_column("Version", no_wrap=True)
        table.add_column("Exists externally", no_wrap=True)
        table.add_column("Equal to external", no_wrap=True)

        # Sort the entities in the following order:
        # 1. Namespace
        # 2. Name
        # 3. Version (reversed)

        successes.sort(
            key=lambda valid_entity: _get_namespace_name_version(valid_entity.entity)
        )

        last_namespace, last_name = "", ""
        for valid_entity in successes:
            namespace, name, version = _get_namespace_name_version(valid_entity.entity)

            if namespace != last_namespace:
                # Add line in table
                table.add_section()

            table.add_row(
                namespace if namespace != last_namespace else "",
                name if name != last_name or namespace != last_namespace else "",
                version,
                {True: "Yes", False: "No", None: "Unknown"}[
                    valid_entity.exists_remotely
                ],
                {
                    True: "Yes",
                    False: "No",
                    None: "Unknown" if no_external_calls else "-",
                }[valid_entity.equal_to_remote],
            )

            last_namespace, last_name = namespace, name

        # Print a horizontal line (rule) before the table
        print("", Rule(title="[bold green]Valid Entities[/bold green]"), "", table, "")

        ## Print detailed differences between the external and local entities

        differing_entities: list[tuple[str, str]] = [
            (get_uri(valid_entity.entity), valid_entity.pretty_diff)
            for valid_entity in successes
            if valid_entity.pretty_diff is not None
        ]

        if differing_entities:
            if verbose:
                print(
                    "\n[bold blue]Detailed differences in validated entities:"
                    "[/bold blue]"
                )

                for uri, pretty_diff in differing_entities:
                    print("", Rule(title=uri), f"\n{pretty_diff}")
            else:
                print(
                    "\n[bold blue]Use the option '--verbose' to see the differences "
                    "between the external and local entities.[/bold blue]"
                )

    else:
        print(
            "\n[bold yellow]There were no valid entities among the supplied "
            "sources.[/bold yellow]\n"
        )

    if not (failed_filepaths or failed_entities):
        return [valid_entity.entity for valid_entity in successes]

    raise typer.Exit(1)
