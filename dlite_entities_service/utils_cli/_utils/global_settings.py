"""Global settings for the CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

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

# Type Aliases
OptionalBool = Optional[bool]


def print_version(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"dlite-entities-service version: {__version__}")
        raise typer.Exit()


def global_options(
    _: Annotated[
        OptionalBool,
        typer.Option(
            "--version",
            help="Show version and exit",
            is_eager=True,
            callback=print_version,
        ),
    ] = None,
    use_service_dotenv: Annotated[
        bool,
        typer.Option(
            "--use-service-dotenv/--use-cli-dotenv",
            help=(
                "Use the .env file also used for the DLite Entities Service or one "
                "only for the CLI."
            ),
            is_flag=True,
            rich_help_panel="Global options",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help=(
                "Print output as JSON. (Muting mutually exclusive with --yaml/--yml "
                "and --json-one-line.)"
            ),
            is_flag=True,
            rich_help_panel="Global options",
        ),
    ] = False,
    as_json_one_line: Annotated[
        bool,
        typer.Option(
            "--json-one-line",
            help=(
                "Print output as JSON without new lines. (Muting mutually exclusive "
                "with --yaml/--yml and --json.)"
            ),
            is_flag=True,
            rich_help_panel="Global options",
        ),
    ] = False,
    as_yaml: Annotated[
        bool,
        typer.Option(
            "--yaml",
            "--yml",
            help=(
                "Print output as YAML. (Mutually exclusive with --json and "
                "--json-one-line.)"
            ),
            is_flag=True,
            rich_help_panel="Global options",
        ),
    ] = False,
) -> None:
    """Global options for the CLI."""
    STATUS["use_service_dotenv"] = use_service_dotenv

    if sum(int(_) for _ in [as_json, as_json_one_line, as_yaml]) > 1:
        raise typer.BadParameter(
            "Cannot use --json, --yaml/--yml, and --json-one-line together in any "
            "combination."
        )
    STATUS["as_json"] = as_json
    STATUS["as_json_one_line"] = as_json_one_line
    STATUS["as_yaml"] = as_yaml
