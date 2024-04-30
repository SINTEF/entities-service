"""entities-service upload command."""

from __future__ import annotations

import json
import re
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

from pydantic import AnyHttpUrl

from entities_service.cli._utils.generics import (
    ERROR_CONSOLE,
    get_namespace_name_version,
    oauth,
    print,
)
from entities_service.cli._utils.types import (
    EntityFileFormats,
    OptionalListEntityFileFormats,
    OptionalListPath,
)
from entities_service.cli.commands.login import login
from entities_service.cli.commands.validate import validate
from entities_service.models import (
    URI_REGEX,
    get_updated_version,
    get_uri,
    get_version,
)
from entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    from entities_service.cli._utils.types import ValidEntity


def upload(
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
            help="Stop uploading entities on the first error during file validation.",
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
            help=(
                "Do not print anything on success and do not ask for confirmation. "
                "IMPORTANT, for content conflicts the defaults will be chosen."
            ),
            show_default=True,
        ),
    ] = False,
    auto_confirm: Annotated[
        bool,
        typer.Option(
            "--auto-confirm",
            "-y",
            help=(
                "Automatically agree to any confirmations and use defaults for "
                "content conflicts. This differs from --quiet in that "
                "it will still print information."
            ),
            show_default=False,
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help=(
                "Strict validation of entities. This means the command will fail "
                "during the validation process, if an external entity already exists "
                "and the two entities are not equal. This option is only relevant if "
                "'--no-external-calls' is not provided. If both '--no-external-calls'"
                " and this options is provided, an error will be emitted."
            ),
            show_default=True,
        ),
    ] = False,
) -> None:
    """Upload (local) entities to a remote location."""
    # Ensure the user is logged in
    login(quiet=True)

    # Validate the entities before uploading
    valid_entities = validate(
        sources=sources,
        filepaths=filepaths,
        directories=directories,
        file_formats=file_formats,
        fail_fast=fail_fast,
        quiet=quiet,
        no_external_calls=False,
        return_full_info=True,
        verbose=False,
        strict=strict,
    )

    # Sanity check - done only for typing to be caught by mypy and testing
    if TYPE_CHECKING:  # pragma: no cover
        assert isinstance(valid_entities, list)  # nosec
        assert all(
            isinstance(entity, ValidEntity) for entity in valid_entities
        )  # nosec

    failed: list[str] = []  # Entity URIs
    successes: list[dict[str, Any]] = []  # Dumped and cleaned entities

    # Evaluate each unique entity
    for valid_entity in valid_entities:

        ## Possibly update new entity according to a comparison with the external,
        ## existing entity
        if valid_entity.exists_remotely:
            if valid_entity.equal_to_remote:
                if not quiet:
                    print(
                        "[bold blue]Info[/bold blue]: Entity already exists externally."
                        f" Skipping entity: {get_uri(valid_entity.entity)}"
                    )
                continue

            if not quiet:
                print(
                    "[bold blue]Info[/bold blue]: Entity already exists externally, "
                    "but it differs in its content.\nDifference between "
                    "external (existing) entity (first) and incoming (new) entity "
                    f"(second) {get_uri(valid_entity.entity)}:"
                    f"\n\n{valid_entity.pretty_diff}\n"
                )

            if quiet or auto_confirm:
                # Use default / auto confirm
                update_version = True
            else:
                try:
                    update_version = typer.confirm(
                        "You cannot overwrite external existing entities. Do you "
                        "wish to upload the new entity with an updated version "
                        "number?",
                        default=True,
                    )
                except typer.Abort:  # pragma: no cover
                    # Can only happen if the user presses Ctrl-C, which can not be
                    # tested currently
                    update_version = False

            if not update_version:
                if not quiet:
                    print(
                        "[bold blue]Info[/bold blue]: Skipping entity: "
                        f"{get_uri(valid_entity.entity)}\n"
                    )
                continue

            if quiet or auto_confirm:
                # Use default / auto confirm
                new_version = get_updated_version(valid_entity.entity)

                if not quiet:
                    print(
                        "[bold blue]Info[/bold blue]: Updating the to-be-uploaded "
                        f"entity to specified version: {new_version}."
                    )
            else:
                # Passing incoming entity-as-model here, since the URIs (and thereby the
                # versions) have already been determined to be the same, and the
                # function only accepts models.
                try:
                    new_version = typer.prompt(
                        "The external existing entity's version is "
                        f"{get_version(valid_entity.entity)!r}. Please enter the new "
                        "version",
                        default=get_updated_version(valid_entity.entity),
                        type=str,
                    )
                except typer.Abort:  # pragma: no cover
                    # Can only happen if the user presses Ctrl-C, which can not be
                    # tested currently
                    if not quiet:
                        print(
                            "[bold blue]Info[/bold blue]: Skipping entity: "
                            f"{get_uri(valid_entity.entity)}\n"
                        )
                    continue

            # Validate new version
            error_message = ""
            if new_version == get_version(valid_entity.entity):
                error_message = (
                    "[bold red]Error[/bold red]: Could not update entity. "
                    f"New version ({new_version}) is the same as the existing "
                    "version.\n"
                )
            elif re.match(r"^\d+(?:\.\d+){0,2}$", new_version) is None:
                error_message = (
                    "[bold red]Error[/bold red]: Could not update entity. "
                    f"New version ({new_version}) is not a valid SOFT version.\n"
                )

            if error_message:
                ERROR_CONSOLE.print(error_message)
                if fail_fast:
                    raise typer.Exit(1)
                failed.append(get_uri(valid_entity.entity))
                continue

            # Update version and URI
            if valid_entity.entity.version is not None:
                valid_entity.entity.version = new_version
                valid_entity.entity.uri = AnyHttpUrl(
                    f"{valid_entity.entity.namespace}/{new_version}/{valid_entity.entity.name}"
                )

            if valid_entity.entity.uri is not None:
                match = URI_REGEX.match(str(valid_entity.entity.uri))

                # match will always be a match object, since the URI has already been
                # validated by the model
                if TYPE_CHECKING:  # pragma: no cover
                    assert match is not None  # nosec

                valid_entity.entity.uri = AnyHttpUrl(
                    f"{match.group('namespace')}/{new_version}/{match.group('name')}"
                )

        # Prepare entity for upload
        # Specifically, rename '$ref' keys to 'ref'
        dumped_entity = valid_entity.entity.model_dump(
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

        successes.append(dumped_entity)

    # Exit if errors occurred
    if failed:
        ERROR_CONSOLE.print(
            f"[bold red]Failed to upload {len(failed)} "
            f"entit{'y' if len(failed) == 1 else 'ies'}, see above for more "
            "details:[/bold red]\n  " + "\n  ".join(failed)
        )
        raise typer.Exit(1)

    if successes:
        if not quiet:
            # Have the user confirm the list of entities to upload
            table = Table(
                expand=True,
                box=box.HORIZONTALS,
                show_edge=False,
                highlight=True,
            )

            table.add_column("Namespace", no_wrap=True)
            table.add_column("Entity", no_wrap=True)

            # Sort the entities in the following order:
            # 1. Namespace
            # 2. Name
            # 3. Version (reversed)

            successes.sort(key=lambda entity: get_namespace_name_version(entity))

            last_namespace = ""
            for entity in successes:
                namespace, name, version = get_namespace_name_version(entity)

                if namespace != last_namespace:
                    # Add line in table
                    table.add_section()

                table.add_row(
                    namespace if namespace != last_namespace else "",
                    f"{name} (v{version})",
                )

            print(
                "",
                Rule(title="[bold green]Entities to upload[/bold green]"),
                "",
                table,
                "",
            )

            if not auto_confirm:
                try:
                    upload_entities = typer.confirm(
                        "These entities will be uploaded. Do you want to continue?",
                        default=True,
                    )
                except typer.Abort as exc:  # pragma: no cover
                    # Can only happen if the user presses Ctrl-C, which can not be
                    # tested currently
                    # Take an Abort as a "no"
                    print("[bold blue]Aborted: No entities were uploaded.[/bold blue]")
                    raise typer.Exit() from exc
            else:
                # Auto confirm
                upload_entities = True

            if not upload_entities:
                print("[bold blue]No entities were uploaded.[/bold blue]")
                raise typer.Exit()

        # Upload entities
        with httpx.Client(base_url=str(CONFIG.base_url), auth=oauth) as client:
            try:
                response = client.post("/_admin/create", json=successes)
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
                f"entit{'y' if len(successes) == 1 else 'ies'}"
            )

    elif not quiet:
        print("[bold blue]No entities were uploaded.[/bold blue]")
