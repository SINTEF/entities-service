"""Typer CLI for doing Entities Service stuff."""

from __future__ import annotations

try:
    import typer
except ImportError as exc:  # pragma: no cover
    from entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

from entities_service.cli._utils.global_settings import global_options
from entities_service.cli.commands import get_commands, get_subtyper_apps

APP = typer.Typer(
    name="entities-service",
    help="Entities Service utility CLI",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    callback=global_options,
)

# Add sub-Typer apps (sub-command groups)
for typer_app, typer_app_kwargs in get_subtyper_apps():
    APP.add_typer(typer_app, **typer_app_kwargs)

# Add all "leaf"-commands
for command, commands_kwargs in get_commands():
    APP.command(**commands_kwargs)(command)
