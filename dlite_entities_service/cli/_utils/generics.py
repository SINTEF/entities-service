"""Various generic constants and functions used by the CLI."""
from __future__ import annotations

import difflib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import httpx
    import rich.pretty
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Please install the DLite entities service utility CLI with 'pip install "
        f"{Path(__file__).resolve().parent.parent.parent.parent.resolve()}[cli]'"
    ) from exc

from rich import get_console
from rich import print as rich_print
from rich.console import Console

from dlite_entities_service.models.auth import Token
from dlite_entities_service.service.config import CONFIG

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

LOGGER = logging.getLogger(__name__)


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
        with httpx.Client(base_url=str(CONFIG.base_url)) as client:
            try:
                response = client.get(
                    "/_admin/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
            except httpx.HTTPError as exc:
                LOGGER.error("Could not validate cached access token.")
                LOGGER.exception(exc)
                # No longer valid
                token_path.unlink()
                return None

        if response.is_success:
            return Token(access_token=token)

        # Not a successful response, so the token is no longer valid
        token_path.unlink()
        return None

    return None


def cache_access_token(token: str | Token) -> None:
    """Cache the access token."""
    if isinstance(token, Token):
        token = token.access_token

    CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    token_path = CACHE_DIRECTORY / "access_token"
    token_path.write_text(token)

    LOGGER.debug("Cached access token at %s.", token_path)
