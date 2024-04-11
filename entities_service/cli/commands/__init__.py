"""All CLI commands."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Generator
    from typing import Any


def get_commands() -> Generator[tuple[Callable, dict[str, Any]], None, None]:
    """Return all CLI commands, along with typer.command() kwargs."""
    this_dir = Path(__file__).parent.resolve()

    for path in this_dir.glob("*.py"):
        if path.stem == "__init__":
            continue

        module = import_module(f".{path.stem}", __package__)

        if not hasattr(module, path.stem):
            raise RuntimeError(
                f"Module {module.__name__} must have a command function with the same "
                "name."
            )

        command_kwargs = {}
        if path.stem in ("upload", "validate"):
            command_kwargs["no_args_is_help"] = True

        yield getattr(module, path.stem), command_kwargs
