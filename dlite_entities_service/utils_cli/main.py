"""Typer CLI for doing DLite entities service stuff."""
from pathlib import Path

try:
    import typer
except ImportError as exc:
    raise ImportError(
        "Please install the DLite entities service utility CLI with "
        f"'pip install {Path(__file__).resolve().parent.parent.parent.resolve()}[cli]'"
    ) from exc

APP = typer.Typer(
    name="entities-service",
    help="DLite entities service utility CLI",
)
