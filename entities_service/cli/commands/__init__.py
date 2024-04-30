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


SUB_TYPER_APPS = ("config",)


def get_commands() -> Generator[tuple[Callable, dict[str, Any]], None, None]:
    """Return all CLI commands, along with typer.command() kwargs."""
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

        command_kwargs = {}
        if path.stem in ("upload", "validate"):
            command_kwargs["no_args_is_help"] = True

        yield getattr(module, path.stem), command_kwargs


def get_subtyper_apps() -> Generator[tuple[Typer, dict[str, Any]], None, None]:
    """Return all CLI Typer apps, which are a group of sub-command groups, along with
    typer.add_typer() kwargs."""
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
