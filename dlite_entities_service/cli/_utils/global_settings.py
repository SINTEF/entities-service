"""Global settings for the CLI."""
from __future__ import annotations

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

# Type Aliases
OptionalBool = Optional[bool]


def print_version(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"dlite-entities-service version: {__version__}")
        raise typer.Exit()


def global_options(
    _: OptionalBool = typer.Option(
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
            "Use the .env file also used for the DLite Entities Service or one "
            "only for the CLI."
        ),
        is_flag=True,
        rich_help_panel="Global options",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help=(
            "Print output as JSON. (Muting mutually exclusive with --yaml/--yml "
            "and --json-one-line.)"
        ),
        is_flag=True,
        rich_help_panel="Global options",
    ),
    as_json_one_line: bool = typer.Option(
        False,
        "--json-one-line",
        help=(
            "Print output as JSON without new lines. (Muting mutually exclusive "
            "with --yaml/--yml and --json.)"
        ),
        is_flag=True,
        rich_help_panel="Global options",
    ),
    as_yaml: bool = typer.Option(
        False,
        "--yaml",
        "--yml",
        help=(
            "Print output as YAML. (Mutually exclusive with --json and "
            "--json-one-line.)"
        ),
        is_flag=True,
        rich_help_panel="Global options",
    ),
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
