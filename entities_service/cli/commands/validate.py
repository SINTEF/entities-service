"""entities-service validate command."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

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

from entities_service.cli._utils.generics import (
    ERROR_CONSOLE,
    get_namespace_name_version,
    pretty_compare_dicts,
    print,
)
from entities_service.cli._utils.types import (
    EntityFileFormats,
    OptionalListEntityFileFormats,
    OptionalListPath,
    ValidEntity,
)
from entities_service.models import (
    Entity,
    get_uri,
    soft_entity,
)

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any


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
    # Hidden options - used only when calling the function directly
    return_full_info: bool = typer.Option(
        False,
        hidden=True,
        help=(
            "Return the full information of the validated entities, i.e., "
            "the `ValidEntity` tuple."
        ),
    ),
) -> Sequence[Entity] | Sequence[ValidEntity]:
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
                    f"{file_format!r} can be handled by adding the option: "
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
                " a single or a list of potential SOFT entities."
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
            return (
                successes
                if return_full_info
                else [valid_entity.entity for valid_entity in successes]  # type: ignore[misc]
            )

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
            key=lambda valid_entity: get_namespace_name_version(valid_entity.entity)
        )

        last_namespace, last_name = "", ""
        for valid_entity in successes:
            namespace, name, version = get_namespace_name_version(valid_entity.entity)

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
                    print("", Rule(title=uri), f"\n{pretty_diff}\n")
            elif not quiet and not return_full_info:
                print(
                    "\n[bold blue]Use the option '--verbose' to see the differences "
                    "between the external and local entities.[/bold blue]\n"
                )

    else:
        print(
            "\n[bold yellow]There were no valid entities among the supplied "
            "sources.[/bold yellow]\n"
        )

    if not (failed_filepaths or failed_entities):
        return (
            successes
            if return_full_info
            else [valid_entity.entity for valid_entity in successes]  # type: ignore[misc]
        )

    raise typer.Exit(1)
