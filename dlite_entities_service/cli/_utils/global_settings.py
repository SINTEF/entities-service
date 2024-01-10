"""Global settings for the CLI."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

try:
    import typer
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Please install the DLite entities service utility CLI with 'pip install "
        f"{Path(__file__).resolve().parent.parent.parent.parent.resolve()}[cli]'"
    ) from exc


from dlite_entities_service import __version__
from dlite_entities_service.cli._utils.generics import (
    get_cached_access_token,
    print,
)
from dlite_entities_service.models.auth import Token
from dlite_entities_service.service.config import CONFIG

if TYPE_CHECKING:  # pragma: no cover
    from typing import TypedDict

    class ContextDict(TypedDict):
        """Global context for the CLI."""

        dotenv_path: Path
        token: Token | None


CONTEXT: ContextDict = {
    "dotenv_path": (Path().cwd() / str(CONFIG.model_config["env_file"])).resolve(),
    "token": get_cached_access_token(),
}
"""Global context for the CLI used to communicate global options."""

# Type Aliases
OptionalBool = Optional[bool]
OptionalPath = Optional[Path]
OptionalStr = Optional[str]


def print_version(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"dlite-entities-service version: {__version__}")
        raise typer.Exit()


def global_options(
    _: OptionalBool = typer.Option(
        None,
        "--version",
        help="Show version and exit.",
        is_eager=True,
        callback=print_version,
    ),
    dotenv_path: OptionalPath = typer.Option(
        CONTEXT["dotenv_path"],
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
    token: OptionalStr = typer.Option(
        None,
        "--token",
        help="The token to use for authentication.",
        show_default=False,
        rich_help_panel="Global options",
    ),
) -> None:
    """Global options for the CLI."""
    if dotenv_path:
        CONTEXT["dotenv_path"] = dotenv_path

    if token:
        access_token = Token(access_token=token)

        # I cannot come up with a scenario where this would not validate.
        # The only scenario in which it would happen is if `token` is not a string.
        # But it can never not be a string due to the way the input is parsed.
        # Even the `if token:` sentence ensures that it will never be an empty string at
        # that...
        # However, should a case ever come up, the following lines should be the
        # 'except' part of a 'try/except'-block for generating the `Token()`:

        # except ValidationError as exc:
        #     raise typer.BadParameter(
        #         f"Invalid token: {token}",
        #         param=token,
        #         param_hint="Token should be given as a string.",
        #     ) from exc

        CONTEXT["token"] = access_token
