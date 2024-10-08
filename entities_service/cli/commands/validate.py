"""entities-service validate command."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

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
    sources: Annotated[
        OptionalListPath,
        typer.Argument(
            metavar="[SOURCE]...",
            help="Path to file or directory with one or more entities.",
            exists=False,
            file_okay=True,
            dir_okay=True,
            readable=True,
            resolve_path=False,
            allow_dash=True,
            show_default=False,
        ),
    ] = None,
    filepaths: Annotated[  # deprecated (in favor of SOURCE)
        OptionalListPath,
        typer.Option(
            "--file",
            "-f",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help=(
                "Path to file with one or more entities. [bold][red]Deprecated[/bold] "
                "instead pass in a filepath as an argument (SOURCE)[/red]."
            ),
            show_default=False,
            hidden=True,
        ),
    ] = None,
    directories: Annotated[  # deprecated (in favor of SOURCE)
        OptionalListPath,
        typer.Option(
            "--dir",
            "-d",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help=(
                "Path to directory with files that include one or more entities. "
                "Subdirectories will be ignored. [bold][red]Deprecated[/bold] "
                "instead pass in a directory as an argument (SOURCE)[/red]."
            ),
            show_default=False,
            hidden=True,
        ),
    ] = None,
    file_formats: Annotated[
        OptionalListEntityFileFormats,
        typer.Option(
            "--format",
            help="Format of entity file(s).",
            show_choices=True,
            show_default=True,
            case_sensitive=False,
        ),
    ] = [EntityFileFormats.JSON],
    fail_fast: Annotated[
        bool,
        typer.Option(
            "--fail-fast",
            help="Stop validating entities on the first discovered error.",
            show_default=True,
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "--silent",
            "-q",
            "-s",
            "-y",
            help="Do not print anything on success.",
            show_default=True,
        ),
    ] = False,
    no_external_calls: Annotated[
        bool,
        typer.Option(
            "--no-external-calls",
            help=(
                "Do not make any external calls to validate the entities. This "
                "includes mainly comparing local entities with their remote "
                "counterparts."
            ),
            show_default=True,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help=(
                "Print the differences between the external and local entities "
                "(if any)."
            ),
            show_default=True,
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help=(
                "Strict validation of entities. This means validation will fail if "
                "an external entity already exists and the two entities are not equal. "
                "This option is only relevant if '--no-external-calls' is not provided."
                " If both '--no-external-calls' and this options is provided, an error "
                "will be emitted."
            ),
            show_default=True,
        ),
    ] = False,
    # Hidden options - used only when calling the function directly
    return_full_info: Annotated[
        bool,
        typer.Option(
            hidden=True,
            help=(
                "Return the full information of the validated entities, i.e., "
                "the `ValidEntity` tuple."
            ),
        ),
    ] = False,
) -> Sequence[Entity] | Sequence[ValidEntity]:
    """Validate (local) entities."""
    unique_sources = set(sources or [])
    unique_file_formats = set(file_formats or [])

    # Include values from deprecated options
    unique_filepaths = set(filepaths or [])
    unique_directories = set(directories or [])

    ## Initial checks

    if not (sources or filepaths or directories):
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Please, provide at least one SOURCE."
        )
        raise typer.Exit(1)

    # --file/-f and --dir/-d are depcrecated in favor of SOURCE
    if unique_filepaths:
        print(
            "[bold yellow]Warning[/bold yellow]: The option '--file/-f' is deprecated. "
            "Please, use a SOURCE instead."
        )
    if unique_directories:
        print(
            "[bold yellow]Warning[/bold yellow]: The option '--dir/-d' is deprecated. "
            "Please, use a SOURCE instead."
        )

    if no_external_calls and strict:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: The options '--no-external-calls' and "
            "'--strict' can not be used together."
        )
        raise typer.Exit(1)

    # Handle YAML/YML file format, ensuring both YAML and YML are in the set
    if unique_file_formats & {EntityFileFormats.YAML, EntityFileFormats.YML}:
        unique_file_formats |= {EntityFileFormats.YAML, EntityFileFormats.YML}

    ## Consolidate provided directories and filepaths

    # stdin
    stdin_variations = [Path(_) for _ in ("-", "/dev/stdin", "CONIN$", "CON")]
    if any(stdin_variation in unique_sources for stdin_variation in stdin_variations):
        source_input_regex = re.compile(r"\"([^\"]*)\"|'([^']*)'|([^\s]+)")

        # Add filepaths and directory paths from stdin
        for line in sys.stdin.readlines():
            for match in source_input_regex.findall(line):
                unique_sources |= {Path(source) for source in match if source}

    # Validate and sort sources according to type
    for source in unique_sources:
        if source in stdin_variations:
            # This is a stdin path and has been dealt with above
            continue

        resolved_source = source.resolve()

        if not resolved_source.exists():
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Path '{source}' does not exist."
            )
            raise typer.Exit(1)

        if resolved_source.is_file():
            unique_filepaths.add(resolved_source)
        elif resolved_source.is_dir():
            unique_directories.add(resolved_source)
        else:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Path '{source}' is not a file or "
                "directory."
            )
            raise typer.Exit(1)

    for directory in unique_directories:
        for root, _, files in os.walk(directory):
            unique_filepaths |= {
                Path(root) / filename
                for filename in files
                if filename.lower().endswith(
                    tuple(
                        f".{file_format}".lower() for file_format in unique_file_formats
                    )
                )
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

        if (file_format := filepath.suffix[1:].lower()) not in unique_file_formats:
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
        with httpx.Client(follow_redirects=True, timeout=10) as client:
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
            pretty_diff = pretty_compare_dicts(external_entity, dumped_entity)
            successes.append(ValidEntity(entity_model, True, False, pretty_diff))

            if strict:
                ERROR_CONSOLE.print(
                    f"[bold red]Error[/bold red]: Entity {get_uri(entity_model)} "
                    "already exists externally and differs in its contents."
                )

                if fail_fast:
                    if verbose:
                        ERROR_CONSOLE.print(
                            "\n[bold blue]Detailed differences:[/bold blue]"
                        )
                        ERROR_CONSOLE.print(
                            "", Rule(title=get_uri(entity_model)), f"\n{pretty_diff}\n"
                        )
                    elif not quiet and not return_full_info:
                        ERROR_CONSOLE.print(
                            "\n[bold blue]Use the option '--verbose' to see the "
                            "difference between the external and local entity."
                            "[/bold blue]\n"
                        )

                    raise typer.Exit(1)

                failed_entities.append(get_uri(entity_model))

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
            box=box.HORIZONTALS,
            show_edge=False,
            highlight=True,
        )

        table.add_column("Namespace", no_wrap=False)
        table.add_column("Name", no_wrap=True)
        table.add_column("Version", no_wrap=True)
        table.add_column("Exists externally", no_wrap=False)
        table.add_column("Equal to external", no_wrap=False)

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
                    False: (
                        "[bold red]No[/bold red] (error in strict-mode)"
                        if strict
                        else "No"
                    ),
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

    if failed_filepaths or failed_entities:
        raise typer.Exit(1)

    return (
        successes
        if return_full_info
        else [valid_entity.entity for valid_entity in successes]  # type: ignore[misc]
    )
