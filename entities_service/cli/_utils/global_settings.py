"""Global settings for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

try:
    import typer
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Please install the entities service utility CLI with 'pip install "
        f"{Path(__file__).resolve().parent.parent.parent.parent.resolve()}[cli]'"
    ) from exc

from entities_service import __version__
from entities_service.cli._utils.generics import CACHE_DIRECTORY, ERROR_CONSOLE, print
from entities_service.cli._utils.types import OptionalBool, OptionalPath
from entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import TypedDict

    class ContextDict(TypedDict):
        """Global context for the CLI."""

        dotenv_path: Path


CONTEXT: ContextDict = {
    "dotenv_path": Path(str(CONFIG.model_config["env_file"])),
}
"""Global context for the CLI used to communicate global options."""


def print_version(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"entities-service version: {__version__}")
        raise typer.Exit()


def global_options(
    _: Annotated[
        OptionalBool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            is_eager=True,
            callback=print_version,
        ),
    ] = None,
    dotenv_path: Annotated[
        OptionalPath,
        typer.Option(
            "--dotenv-config",
            exists=False,
            dir_okay=False,
            file_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
            help=(
                "Use the .env file at the given location for the current command. "
                "By default it will point to the .env file in the current directory."
            ),
            show_default=True,
            rich_help_panel="Global options",
        ),
    ] = CONTEXT["dotenv_path"],
) -> None:
    """Global options for the CLI.

    This function is also used to run initial setup for the CLI.
    """
    if dotenv_path:
        CONTEXT["dotenv_path"] = dotenv_path

    # Initialize the cache directory
    try:
        CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: {CACHE_DIRECTORY} is not writable. "
            "Please check your permissions."
        )
        raise typer.Exit(1) from exc
