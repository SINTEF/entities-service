"""entities-service list command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

try:
    import httpx
    import typer
    from rich import box
    from rich.table import Table
except ImportError as exc:  # pragma: no cover
    from entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

from pydantic import ValidationError
from pydantic.networks import AnyUrl

from entities_service.cli._utils.generics import (
    ERROR_CONSOLE,
    get_namespace_name_version,
    print,
)
from entities_service.cli._utils.types import OptionalListStr
from entities_service.models import URI_REGEX, soft_entity
from entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from entities_service.models import Entity


APP = typer.Typer(
    name=__file__.rsplit("/", 1)[-1].replace(".py", ""),
    help="List resources.",
    no_args_is_help=True,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@APP.command()
def namespaces(
    # Hidden options - used only when calling the function directly
    return_info: Annotated[
        bool,
        typer.Option(
            hidden=True,
            help=(
                "Avoid printing the namespaces and instead return them as a Python "
                "list. Useful when calling this function from another function."
            ),
        ),
    ] = False,
) -> list[str] | None:
    """List namespaces from the entities service."""
    with httpx.Client(base_url=str(CONFIG.base_url)) as client:
        try:
            response = client.get("/_api/namespaces")
        except httpx.HTTPError as exc:
            ERROR_CONSOLE.print(
                "[bold red]Error[/bold red]: Could not list namespaces. HTTP "
                f"exception: {exc}"
            )
            raise typer.Exit(1) from exc

    if not response.is_success:
        try:
            error_message = response.json()
        except json.JSONDecodeError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not list namespaces. JSON decode "
                f"error: {exc}"
            )
            raise typer.Exit(1) from exc

        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: Could not list namespaces. HTTP status code: "
            f"{response.status_code}. Error response: "
        )
        ERROR_CONSOLE.print_json(data=error_message)
        raise typer.Exit(1)

    namespaces: list[str] = response.json()

    if not namespaces:  # pragma: no cover
        # This will never be reached, since the server will always return at least one
        # namespace (the "core" namespace)
        # This is kept here for completeness
        ERROR_CONSOLE.print("[bold red]Error[/bold red]: No namespaces found.")
        raise typer.Exit(1)

    if return_info:
        return namespaces

    # Print namespaces
    table = Table(
        box=box.HORIZONTALS,
        show_edge=False,
        highlight=True,
    )

    table.add_column("Namespaces:", no_wrap=True)

    for namespace in sorted(namespaces):
        table.add_row(namespace)

    print("", table, "")

    return None


@APP.command()
def entities(
    namespace: Annotated[
        OptionalListStr,
        typer.Argument(
            help=(
                "Namespace(s) to list entities from. Defaults to the core namespace. "
                "If the namespace is a URL, the specific namespace will be extracted."
            ),
            show_default=False,
        ),
    ] = None,
    all_namespaces: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="List entities from all namespaces.",
        ),
    ] = False,
) -> None:
    """List entities from the entities service."""
    valid_namespaces: list[str] = namespaces(return_info=True)

    if all_namespaces:
        namespace = valid_namespaces

    if namespace is None:
        namespace = [str(CONFIG.base_url).rstrip("/")]

    try:
        target_namespaces = [_parse_namespace(ns) for ns in namespace]
    except ValueError as exc:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Invalid namespace given: " f"{exc}"
        )
        raise typer.Exit(1) from exc

    if not all(ns in valid_namespaces for ns in target_namespaces):
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Invalid namespace(s) given: "
            f"{[ns for ns in target_namespaces if ns not in valid_namespaces]}"
        )
        raise typer.Exit(1)

    # Get all specific namespaces from target namespaces (including "core", if present)
    # `specific_namespaces` will consist of specific namespaces (str)
    # and/or the "core" namespace (None)
    specific_namespaces = [_get_specific_namespace(ns) for ns in target_namespaces]

    with httpx.Client(base_url=str(CONFIG.base_url)) as client:
        try:
            response = client.get(
                "/_api/entities",
                params={
                    "namespace": [
                        ns if ns is not None else "" for ns in specific_namespaces
                    ]
                },
            )
        except httpx.HTTPError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not list entities. HTTP exception: "
                f"{exc}"
            )
            raise typer.Exit(1) from exc

    if not response.is_success:
        try:
            error_message = response.json()
        except json.JSONDecodeError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not list entities. JSON decode "
                f"error: {exc}"
            )
            raise typer.Exit(1) from exc

        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: Could not list entities. HTTP status code: "
            f"{response.status_code}. Error response: "
        )
        ERROR_CONSOLE.print_json(data=error_message)
        raise typer.Exit(1)

    # We do not need to validate the response, since the server's response model will do
    # that for us
    entities: list[Entity] = [soft_entity(**entity) for entity in response.json()]

    if not entities:
        print(f"No entities found in namespace {namespace}")
        raise typer.Exit()

    # Print entities
    table = Table(
        box=box.HORIZONTALS,
        show_edge=False,
        highlight=True,
    )

    # Sort the entities in the following order:
    # 1. Namespace (only relevant if multiple namespaces are given)
    # 2. Name
    # 3. Version (reversed)

    if len(target_namespaces) > 1:
        table.add_column("Namespace", no_wrap=False)
    table.add_column("Name", no_wrap=True)
    table.add_column("Version", no_wrap=True)

    last_namespace, last_name = "", ""
    for entity in sorted(
        entities, key=lambda entity: get_namespace_name_version(entity)
    ):
        entity_namespace, entity_name, entity_version = get_namespace_name_version(
            entity
        )

        if entity_namespace != last_namespace:
            # Add line in table
            table.add_section()

        if len(target_namespaces) > 1:
            # Include namespace
            table.add_row(
                entity_namespace if entity_namespace != last_namespace else "",
                (
                    entity_name
                    if entity_name != last_name or entity_namespace != last_namespace
                    else ""
                ),
                entity_version,
            )
        else:
            table.add_row(
                entity_name if entity_name != last_name else "",
                entity_version,
            )

        last_namespace, last_name = entity_namespace, entity_name

    core_namespace = str(CONFIG.base_url).rstrip("/")
    single_namespace = ""
    if len(target_namespaces) == 1 and entity_namespace != core_namespace:
        single_namespace = f"Specific namespace: {core_namespace}/{entity_namespace}\n"

    print(f"\nBase namespace: {core_namespace}\n{single_namespace}", table, "")


def _parse_namespace(namespace: str | None) -> str:
    """Parse a (specfic) namespace, returning a full namespace."""
    # If a full URI (including version and name) is passed,
    # extract and return the namespace
    if namespace is not None and (match := URI_REGEX.match(namespace)) is not None:
        return match.group("namespace")

    core_namespace = str(CONFIG.base_url).rstrip("/")

    if namespace is None or (
        isinstance(namespace, str) and namespace.strip() in ("/", "")
    ):
        return core_namespace

    if namespace.startswith(core_namespace):
        return namespace.rstrip("/")

    try:
        AnyUrl(namespace)
    except (ValueError, TypeError, ValidationError):
        # Expect the namespace to be a specific namespace
        return f"{core_namespace}/{namespace.lstrip('/')}"

    # The namespace is a URL, but not within the core namespace
    raise ValueError(f"{namespace} is not within the core namespace {core_namespace}")


def _get_specific_namespace(namespace: str) -> str | None:
    """Retrieve the specific namespace (if any) from a full namespace."""
    namespace = namespace[len(str(CONFIG.base_url).rstrip("/")) :]
    if namespace.strip() in ("/", ""):
        return None
    return namespace.lstrip("/")
