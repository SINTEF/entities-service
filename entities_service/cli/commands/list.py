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


from entities_service.cli._utils.generics import ERROR_CONSOLE, print
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
                f"[bold red]Error[/bold red]: Could not list namespaces. HTTP exception: "
                f"{exc}"
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

    if not namespaces:
        print("No namespaces found")
        raise typer.Exit()

    if return_info:
        return namespaces

    # Print namespaces
    table = Table(
        title="Namespaces:",
        title_style="bold",
        title_justify="left",
        box=box.HORIZONTALS,
        show_edge=False,
        highlight=True,
    )

    table.add_column("Namespace", no_wrap=True)

    for namespace in sorted(namespaces):
        table.add_row(namespace)

    print("", table)

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
    valid_namespaces = namespaces(return_info=True)

    if all_namespaces:
        namespace = valid_namespaces

    if namespace is None:
        namespace = [str(CONFIG.base_url).rstrip("/")]

    namespace: list[None | str] = [_parse_namespace(ns) for ns in namespace]

    if not all(ns in valid_namespaces for ns in namespace):
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Invalid namespace(s) given: "
            f"{[ns for ns in namespace if ns not in valid_namespaces]}"
        )
        raise typer.Exit(1)

    # Namespace is now the specific namespace (str) or the "core" namespace (None)
    path_prefix = f"/{namespace}" if namespace is not None else ""

    with httpx.Client(base_url=str(CONFIG.base_url)) as client:
        try:
            response = client.get(
                f"{path_prefix}/_api/entities",
                params={"namespace": namespace},
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
        title=f"Entities in namespace {namespace}:",
        title_style="bold",
        title_justify="left",
        box=box.HORIZONTALS,
        show_edge=False,
        highlight=True,
    )

    # Sort the entities in the following order:
    # 1. Namespace (only relevant if --all/-a is given)
    # 2. Name
    # 3. Version (reversed)

    if all_namespaces:
        table.add_column("Namespace", no_wrap=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Version", no_wrap=True)

    previous_entity_name = ""
    for entity in sorted(entities, key=lambda entity: entity.name):
        if entity.name == previous_entity_name:
            # Only add the version
            table.add_row("", entity.version)
        else:
            table.add_row(entity.name, entity.version)

        previous_entity_name = entity.name

    print("", table)


def _parse_namespace(namespace: str) -> str | None:
    """Parse the namespace and return the specific namespace (if any)."""
    if (match := URI_REGEX.match(namespace)) is None:
        return namespace

    return match.group("specific_namespace")
