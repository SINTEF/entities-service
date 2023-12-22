"""admin subcommand for dlite-entities-service CLI."""
from __future__ import annotations

import json
from typing import Optional

try:
    import httpx
    import typer
except ImportError as exc:  # pragma: no cover
    from dlite_entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

from pydantic import ValidationError

from dlite_entities_service.cli._utils.generics import ERROR_CONSOLE, print
from dlite_entities_service.models.auth import NewUser, User
from dlite_entities_service.service.config import CONFIG

APP = typer.Typer(
    name=__file__.rsplit("/", 1)[-1].replace(".py", ""),
    help="Perform administrative tasks.",
    no_args_is_help=True,
    invoke_without_command=True,
)

# Type Aliases
OptionalStr = Optional[str]


@APP.command()
def create_user(
    username: OptionalStr = typer.Option(
        None,
        "--username",
        "-u",
        envvar="ENTITY_SERVICE_ADMIN_USER",
        help="Username for user with write acces in the entities service.",
        show_default=False,
    ),
    password: OptionalStr = typer.Option(
        None,
        "--password",
        "-p",
        envvar="ENTITY_SERVICE_ADMIN_PASSWORD",
        help="Password for user with write access in the entities service.",
        show_default=False,
    ),
    full_name: OptionalStr = typer.Option(
        None,
        help="Full name.",
    ),
) -> None:
    """Create a new admin user.

    Note, this command can only create users that already have admin rights in
    the backend. To create a new admin user, you must first create a user with
    admin rights in the backend, and then use this command to create the user
    in the Entities Service.
    """
    if not username:
        username = typer.prompt("Username", type=str)
    if not password:
        password = typer.prompt("Password", type=str, hide_input=True)
    if not full_name:
        full_name = typer.prompt("Full name", default="", show_default=False, type=str)

    user = NewUser(username=username, password=password, full_name=full_name)

    with httpx.Client(base_url=str(CONFIG.base_url)) as client:
        try:
            response = client.post(
                "/_auth/create_user", json=user.model_dump(mode="json")
            )
        except httpx.HTTPError as exc:
            ERROR_CONSOLE.print(
                "[bold red]Error:[/bold red] Could not create user. HTTP exception: "
                f"{exc}"
            )
            raise typer.Exit(1) from exc

    if not response.is_success:
        try:
            error_message = response.json()
        except json.JSONDecodeError as exc:
            ERROR_CONSOLE.print(
                "[bold red]Error[/bold red]: Could not create user. JSON decode "
                f"error: {exc}"
            )
            raise typer.Exit(1) from exc

        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: Could not create user. HTTP status code: "
            f"{response.status_code}. Error message: {error_message}"
        )
        raise typer.Exit(1)

    try:
        created_user = User(**response.json())
    except json.JSONDecodeError as exc:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Could not create user. JSON decode error: "
            f"{exc}"
        )
        raise typer.Exit(1) from exc
    except ValidationError as exc:
        ERROR_CONSOLE.print(
            "[bold red]Error[/bold red]: Could not create user. Validation error: "
            f"{exc}"
        )
        raise typer.Exit(1) from exc

    print(f"[bold gree]Successfully created user:[/bold green]\n{created_user}")
