"""entities-service login command."""

from __future__ import annotations

import json

try:
    import httpx
    import typer
except ImportError as exc:  # pragma: no cover
    from entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

from entities_service.cli._utils.generics import (
    ERROR_CONSOLE,
    AuthenticationError,
    oauth,
    print,
)
from entities_service.service.config import CONFIG


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
