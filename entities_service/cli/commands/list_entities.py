"""entities-service list command."""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING

try:
    import httpx
    import typer
    from rich import box
    from rich.table import Table
except ImportError as exc:  # pragma: no cover
    from entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

from pydantic import AnyHttpUrl, ValidationError

from entities_service.cli._utils.generics import ERROR_CONSOLE, print
from entities_service.cli._utils.types import OptionalStr
from entities_service.models import URI_REGEX, soft_entity
from entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from entities_service.models import Entity


def list_entities(
    namespace: OptionalStr = typer.Option(
        str(CONFIG.base_url).rstrip("/"),
        "--namespace",
        "-n",
        help="Namespace to list entities from.",
        show_default=True,
    )
) -> None:
    """List entities from the entities service."""
    if namespace is None:
        namespace = str(CONFIG.base_url).rstrip("/")

    namespace_as_url: AnyHttpUrl | None = None
    with contextlib.suppress(ValidationError):
        namespace_as_url = AnyHttpUrl(namespace)

    if namespace_as_url is not None:
        # Validate namespace and retrieve the specific namespace (if any)
        if (match := URI_REGEX.match(str(namespace_as_url))) is None:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Namespace {namespace_as_url} does not "
                "match the URI regex."
            )
            raise typer.Exit(1)

        # Replace the namespace with the specific namespace
        # This will be `None` if the namespace is the "core" namespace
        namespace = match.group("specific_namespace")

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
        box=box.SIMPLE_HEAD,
        highlight=True,
    )

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
