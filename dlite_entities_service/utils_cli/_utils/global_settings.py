"""Global settings for the CLI."""
from pathlib import Path
from typing import Optional

try:
    import typer
except ImportError as exc:
    raise ImportError(
        "Please install the DLite entities service utility CLI with 'pip install "
        f"{Path(__file__).resolve().parent.parent.parent.parent.resolve()}[cli]'"
    ) from exc

from rich import print  # pylint: disable=redefined-builtin

from dlite_entities_service import __version__

STATUS = {"use_service_dotenv": False}


def print_version(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"dlite-entities-service version: {__version__}")
        raise typer.Exit()


def global_options(
    _: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit",
        is_eager=True,
        callback=print_version,
    ),
    use_service_dotenv: bool = typer.Option(
        False,
        "--use-service-dotenv/--use-cli-dotenv",
        help=(
            "Use the .env file also used for the DLite Entities Service or one only "
            "for the CLI."
        ),
        is_flag=True,
        rich_help_panel="Global options",
    ),
) -> None:
    """Global options for the CLI."""
    STATUS["use_service_dotenv"] = use_service_dotenv
