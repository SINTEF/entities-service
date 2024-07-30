"""All CLI commands."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

from entities_service.cli._utils.global_settings import global_options

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Generator
    from typing import Any

    from typer import Typer


SUB_TYPER_APPS = ("config", "list")
NO_ARGS_IS_HELP_COMMANDS = ("upload", "validate")
ALIASED_COMMANDS: dict[str, str] = {}


def get_commands() -> Generator[tuple[Callable, dict[str, Any]]]:
    """Return all CLI commands, along with typer.command() kwargs.

    It is important the command module name matches the command function name.

    To have a command with an alias, add the alias to the ALIASED_COMMANDS dict.
    To have a command that does not require arguments to show the help message, add
    the command name to the NO_ARGS_IS_HELP_COMMANDS tuple.
    """
    this_dir = Path(__file__).parent.resolve()

    for path in this_dir.glob("*.py"):
        if path.stem in ("__init__", *SUB_TYPER_APPS):
            continue

        module = import_module(f".{path.stem}", __package__)

        if not hasattr(module, path.stem):  # pragma: no cover
            # This block is not covered in the code coverage, since it is only here to
            # keep developers from making a mistake during development. This will never
            # be an issue at actual runtime (assuming tests are run before deployment).
            raise RuntimeError(
                f"Module {module.__name__} must have a command function with the same "
                "name."
            )

        command_kwargs: dict[str, Any] = {}
        if path.stem in NO_ARGS_IS_HELP_COMMANDS:
            command_kwargs["no_args_is_help"] = True
        if path.stem in ALIASED_COMMANDS:
            command_kwargs["name"] = ALIASED_COMMANDS[path.stem]

        yield getattr(module, path.stem), command_kwargs


def get_subtyper_apps() -> Generator[tuple[Typer, dict[str, Any]]]:
    """Return all CLI Typer apps, which are a group of sub-command groups, along with
    typer.add_typer() kwargs.

    This is done according to the SUB_TYPER_APPS tuple.
    """
    this_dir = Path(__file__).parent.resolve()

    for path in this_dir.glob("*.py"):
        if path.stem not in SUB_TYPER_APPS:
            continue

        module = import_module(f".{path.stem}", __package__)

        if not hasattr(module, "APP"):  # pragma: no cover
            # This block is not covered in the code coverage, since it is only here to
            # keep developers from making a mistake during development. This will never
            # be an issue at actual runtime (assuming tests are run before deployment).
            raise RuntimeError(
                f"Module {module.__name__} must have an 'APP' Typer variable "
                "application."
            )

        app_kwargs = {}
        if path.stem in ("config",):
            app_kwargs["callback"] = global_options

        yield module.APP, app_kwargs
