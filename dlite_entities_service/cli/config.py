"""config subcommand for dlite-entities-service CLI."""
from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Enum with string values."""


try:
    import typer
except ImportError as exc:  # pragma: no cover
    from dlite_entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

import yaml
from dotenv import dotenv_values, set_key, unset_key
from rich import print_json

from dlite_entities_service.cli._utils.generics import ERROR_CONSOLE, print
from dlite_entities_service.cli._utils.global_settings import STATUS
from dlite_entities_service.service.config import CONFIG

CLI_DOTENV_FILE: Path = (
    Path(__file__).resolve().parent / CONFIG.model_config["env_file"]
)
SERVICE_DOTENV_FILE: Path = (
    Path(__file__).resolve().parent.parent.parent / CONFIG.model_config["env_file"]
)

APP = typer.Typer(
    name=__file__.rsplit("/", 1)[-1].replace(".py", ""),
    help="Manage configuration options.",
    no_args_is_help=True,
    invoke_without_command=True,
)

# Type Aliases
OptionalStr = Optional[str]


class ConfigFields(StrEnum):
    """Configuration options."""

    BASE_URL = "base_url"
    MONGO_URI = "mongo_uri"
    MONGO_USER = "mongo_user"
    MONGO_PASSWORD = "mongo_password"  # nosec

    @classmethod
    def autocomplete(cls, incomplete: str) -> Generator[tuple[str, str], None, None]:
        """Return a list of valid configuration options."""
        for member in cls:
            if member.value.startswith(incomplete):
                if member.value not in CONFIG.model_fields:  # pragma: no cover
                    # This block is not covered in the code coverage, since it will
                    # currently never be reached. The current list of configuration
                    # options in CONFIG exactly equals those of the ConfigFields enum.
                    # However, this block is still included for completeness, sanity
                    # checking, and future-proofing.
                    raise typer.BadParameter(
                        f"Invalid configuration option: {member.value!r}"
                    )
                yield member.value, CONFIG.model_fields[member.value].description

    def is_sensitive(self) -> bool:
        """Return True if this is a sensitive configuration option."""
        return self in [ConfigFields.MONGO_PASSWORD]


@APP.command(name="set")
def set_config(
    key: ConfigFields = typer.Argument(
        help=(
            "Configuration option to set. These can also be set as an environment "
            f"variable by prefixing with {CONFIG.model_config['env_prefix'].upper()!r}."
        ),
        show_choices=True,
        shell_complete=ConfigFields.autocomplete,
        case_sensitive=False,
        show_default=False,
    ),
    value: OptionalStr = typer.Argument(
        None,
        help=(
            "Value to set. For sensitive values, this will be prompted for if not "
            "provided."
        ),
        show_default=False,
    ),
) -> None:
    """Set a configuration option."""
    if not value:
        value = typer.prompt(
            f"Enter a value for {key.upper()}", hide_input=key.is_sensitive()
        )
    if STATUS["use_service_dotenv"]:
        dotenv_file = SERVICE_DOTENV_FILE
    else:
        dotenv_file = CLI_DOTENV_FILE
    if not dotenv_file.exists():
        dotenv_file.touch()
    set_key(dotenv_file, f"{CONFIG.model_config['env_prefix']}{key}".upper(), value)
    print(
        (
            f"Set {CONFIG.model_config['env_prefix'].upper()}{key.upper()} to "
            "sensitive value."
        )
        if key.is_sensitive()
        else f"Set {CONFIG.model_config['env_prefix'].upper()}{key.upper()} to {value}."
    )


@APP.command()
def unset(
    key: ConfigFields = typer.Argument(
        help="Configuration option to unset.",
        show_choices=True,
        shell_complete=ConfigFields.autocomplete,
        case_sensitive=False,
        show_default=False,
    ),
) -> None:
    """Unset a single configuration option."""
    if STATUS["use_service_dotenv"]:
        dotenv_file = SERVICE_DOTENV_FILE
    else:
        dotenv_file = CLI_DOTENV_FILE
    if dotenv_file.exists():
        unset_key(dotenv_file, f"{CONFIG.model_config['env_prefix']}{key}".upper())
        print(f"Unset {CONFIG.model_config['env_prefix'].upper()}{key.upper()}.")
    else:
        print(f"{dotenv_file} file not found.")


@APP.command()
def unset_all() -> None:
    """Unset all configuration options."""
    typer.confirm(
        "Are you sure you want to unset (remove) all configuration options in "
        f"{'Service' if STATUS['use_service_dotenv'] else 'CLI'}-specific "
        f"{CONFIG.model_config['env_file']} file?",
        abort=True,
    )

    if STATUS["use_service_dotenv"]:
        dotenv_file = SERVICE_DOTENV_FILE
    else:
        dotenv_file = CLI_DOTENV_FILE
    if dotenv_file.exists():
        dotenv_file.unlink()
        print(f"Unset all configuration options. (Removed {dotenv_file}.)")
    else:
        print(f"{dotenv_file} file not found.")


@APP.command()
def show(
    reveal_sensitive: bool = typer.Option(
        False,
        "--reveal-sensitive",
        help="Reveal sensitive values. (DANGEROUS! Use with caution.)",
        is_flag=True,
        show_default=False,
    ),
) -> None:
    """Show the current configuration."""
    if STATUS["use_service_dotenv"]:
        dotenv_file = SERVICE_DOTENV_FILE
    else:
        dotenv_file = CLI_DOTENV_FILE
    if dotenv_file.exists():
        if not any(STATUS[_] for _ in ["as_json", "as_json_one_line", "as_yaml"]):
            print(f"Current configuration in {dotenv_file}:\n")
        values = {
            ConfigFields(key[len(CONFIG.model_config["env_prefix"]) :].lower()): value
            for key, value in dotenv_values(dotenv_file).items()
            if key
            in [
                f"{CONFIG.model_config['env_prefix']}{_}".upper()
                for _ in ConfigFields.__members__.values()
            ]
        }
    else:
        ERROR_CONSOLE.print(f"No {dotenv_file} file found.")
        raise typer.Exit(1)

    output = {}
    for key, value in values.items():
        sensitive_value = None
        if not reveal_sensitive and key.is_sensitive():
            sensitive_value = "*" * 8
        output[f"{CONFIG.model_config['env_prefix']}{key}".upper()] = (
            sensitive_value or value
        )

    if STATUS["as_json"] or STATUS["as_json_one_line"]:
        print_json(data=output, indent=2 if STATUS["as_json"] else None)
    elif STATUS["as_yaml"]:
        print(yaml.safe_dump(output, sort_keys=False, allow_unicode=True))
    else:
        print(
            "\n".join(
                f"[bold]{key.upper()}[/bold]: {value}" for key, value in output.items()
            )
        )
