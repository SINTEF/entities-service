"""Various generic constants and functions used by the CLI."""
from __future__ import annotations

import difflib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import rich.pretty
    from rich import get_console
    from rich import print as rich_print
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Please install the DLite entities service utility CLI with 'pip install "
        f"{Path(__file__).resolve().parent.parent.parent.parent.resolve()}[cli]'"
    ) from exc

from rich.console import Console

from dlite_entities_service.models.auth import Token
from dlite_entities_service.service.security import get_token_data

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, TextIO


EXC_MSG_INSTALL_PACKAGE = (
    "Please install the DLite entities service utility CLI with "
    f"'pip install {Path(__file__).resolve().parent.parent.parent.parent.resolve()}"
    "[cli]' or 'pip install dlite-entities-service[cli]'"
)

OUTPUT_CONSOLE = get_console()
ERROR_CONSOLE = Console(stderr=True)

CACHE_DIRECTORY: Path = Path(
    os.getenv(
        "ENTITY_SERVICE_CLI_CACHE_DIR", str(Path.home() / ".cache" / "entities-service")
    )
).resolve()
"""The directory where the CLI caches data."""


def print(
    *objects: Any,
    sep: str | None = None,
    end: str | None = None,
    file: TextIO | None = None,
    flush: bool | None = None,
) -> None:
    """Print to the output console."""
    file = file or OUTPUT_CONSOLE.file
    kwargs = {"sep": sep, "end": end, "file": file, "flush": flush}
    for key, value in list(kwargs.items()):
        if value is None:
            del kwargs[key]

    rich_print(*objects, **kwargs)


def pretty_compare_dicts(
    dict_first: dict[Any, Any], dict_second: dict[Any, Any]
) -> str:
    return "\n".join(
        difflib.ndiff(
            rich.pretty.pretty_repr(dict_first).splitlines(),
            rich.pretty.pretty_repr(dict_second).splitlines(),
        ),
    )


def get_cached_access_token() -> Token | None:
    """Return the cached access token."""
    token_path = CACHE_DIRECTORY / "access_token"
    if token_path.exists():
        token = token_path.read_text()

        # Check if the cached token is still valid
        token_data = get_token_data(token)
        if token_data.expires_at is not None and token_data.expires_at > datetime.now(
            tz=timezone.utc
        ):
            # No longer valid
            token_path.unlink()
            return None

        return Token(access_token=token)

    return None


def cache_access_token(token: str | Token) -> None:
    """Cache the access token."""
    if isinstance(token, Token):
        token = token.access_token

    CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    token_path = CACHE_DIRECTORY / "access_token"
    token_path.write_text(token)
