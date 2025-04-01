"""config subcommand for entities-service CLI."""

from __future__ import annotations

from collections.abc import Generator
from functools import cache
from typing import Annotated, get_args

try:
    import typer
except ImportError as exc:  # pragma: no cover
    from entities_service.cli._utils.generics import EXC_MSG_INSTALL_PACKAGE

    raise ImportError(EXC_MSG_INSTALL_PACKAGE) from exc

from dotenv import dotenv_values, set_key, unset_key
from pydantic import SecretBytes, SecretStr

from entities_service.cli._utils.generics import ERROR_CONSOLE, print
from entities_service.cli._utils.global_settings import CONTEXT
from entities_service.cli._utils.types import OptionalStr, StrEnum
from entities_service.service.config import ServiceSettings

APP = typer.Typer(
    name=__file__.rsplit("/", 1)[-1].replace(".py", ""),
    help="Manage configuration options.",
    no_args_is_help=True,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


class ConfigFields(StrEnum):
    """Configuration options."""

    _ignore_ = "ConfigFields config_name"

    ConfigFields = vars()
    for config_name in sorted(ServiceSettings.model_fields):
        ConfigFields[config_name.upper()] = config_name.lower()

    @classmethod
    def autocomplete(cls, incomplete: str) -> Generator[tuple[str, str]]:
        """Return a list of valid configuration options."""
        for member in cls:
            if member.value.startswith(incomplete):
                if member.value not in ServiceSettings.model_fields:  # pragma: no cover
                    # This block is not covered in the code coverage, since it will
                    # currently never be reached. The current list of configuration
                    # options in CONFIG exactly equals those of the ConfigFields enum.
                    # However, this block is still included for completeness, sanity
                    # checking, and future-proofing.
                    raise typer.BadParameter(
                        f"Invalid configuration option: {member.value!r}"
                    )
                yield member.value, ServiceSettings.model_fields[
                    member.value
                ].description

    @classmethod
    @cache
    def sensitive_fields(cls) -> dict[ConfigFields, bool]:  # type: ignore[valid-type]
        """Return a mapping of sensitive configuration options."""
        sensitive_fields: dict[ConfigFields, bool] = {}
        for config_name, field_info in ServiceSettings.model_fields.items():
            annotation = field_info.rebuild_annotation()

            annotation_args = get_args(annotation)

            if annotation_args:
                if any(_ in (SecretStr, SecretBytes) for _ in annotation_args):
                    sensitive_fields[getattr(cls, config_name.upper())] = True
                else:
                    sensitive_fields[getattr(cls, config_name.upper())] = False

            elif annotation in (SecretStr, SecretBytes):  # pragma: no cover
                # Currently there is no config value that fits this test.
                # But we keep it here to be future-proof and more clear about the usage
                # of `typing.get-args()`.
                sensitive_fields[getattr(cls, config_name.upper())] = True

            else:
                sensitive_fields[getattr(cls, config_name.upper())] = False

        return sensitive_fields

    def is_sensitive(self) -> bool:
        """Return True if this is a sensitive configuration option."""
        return self.__class__.sensitive_fields()[self]


@APP.command(name="set")
def set_config(
    key: Annotated[
        ConfigFields,
        typer.Argument(
            help=(
                "Configuration option to set. These can also be set as an environment "
                "variable by prefixing with "
                f"{ServiceSettings.model_config['env_prefix'].upper()!r}."
            ),
            show_choices=True,
            autocompletion=ConfigFields.autocomplete,
            case_sensitive=False,
            show_default=False,
        ),
    ],
    value: Annotated[
        OptionalStr,
        typer.Argument(
            help="Value to set. This will be prompted for if not provided.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Set a configuration option."""
    if not value:
        try:
            value = typer.prompt(
                f"Enter a value for {key.upper()}",
                hide_input=key.is_sensitive(),
                type=str,
            )
        except typer.Abort as exc:  # pragma: no cover
            # Can only happen if the user presses Ctrl-C, which can not be tested
            # currently
            print("[bold blue]Info[/bold blue]: Aborted.")
            raise typer.Exit(1) from exc

    dotenv_file = CONTEXT["dotenv_path"]

    if not dotenv_file.exists():
        dotenv_file.touch()

    set_key(
        dotenv_file, f"{ServiceSettings.model_config['env_prefix']}{key}".upper(), value
    )

    print(
        (
            f"Set {ServiceSettings.model_config['env_prefix'].upper()}{key.upper()} to "
            "sensitive value."
        )
        if key.is_sensitive()
        else (
            f"Set {ServiceSettings.model_config['env_prefix'].upper()}{key.upper()} to "
            f"{value}."
        )
    )


@APP.command()
def show(
    reveal_sensitive: Annotated[
        bool,
        typer.Option(
            "--reveal-sensitive",
            help="Reveal sensitive values. (DANGEROUS! Use with caution.)",
            show_default=False,
        ),
    ] = False,
) -> None:
    """Show the current configuration."""
    dotenv_file = CONTEXT["dotenv_path"]

    if dotenv_file.exists():
        print(f"Current configuration in {dotenv_file}:\n")
        values: dict[ConfigFields, str | None] = {
            ConfigFields(
                key[len(ServiceSettings.model_config["env_prefix"]) :].lower()
            ): value
            for key, value in dotenv_values(dotenv_file).items()
            if key
            in [
                f"{ServiceSettings.model_config['env_prefix']}{_}".upper()
                for _ in ConfigFields.__members__.values()
            ]
        }
    else:
        ERROR_CONSOLE.print(f"No {dotenv_file} file found.")
        raise typer.Exit(1)

    output: dict[str, str | None] = {}
    for key, value in values.items():
        sensitive_value = None

        if not reveal_sensitive and key.is_sensitive():
            sensitive_value = "*" * 8

        output[f"{ServiceSettings.model_config['env_prefix']}{key}".upper()] = (
            sensitive_value or value
        )

    print(
        "\n".join(
            f"[bold]{key.upper()}[/bold]: {value if value is not None else ''}"
            for key, value in output.items()
        )
    )


@APP.command()
def unset(
    key: Annotated[
        ConfigFields,
        typer.Argument(
            help="Configuration option to unset.",
            show_choices=True,
            autocompletion=ConfigFields.autocomplete,
            case_sensitive=False,
            show_default=False,
        ),
    ],
) -> None:
    """Unset a single configuration option."""
    dotenv_file = CONTEXT["dotenv_path"]

    if dotenv_file.exists():
        unset_key(
            dotenv_file, f"{ServiceSettings.model_config['env_prefix']}{key}".upper()
        )
        print(
            f"Unset {ServiceSettings.model_config['env_prefix'].upper()}{key.upper()}."
        )
    else:
        print(f"{dotenv_file} file not found.")


@APP.command()
def unset_all() -> None:
    """Unset all configuration options."""
    dotenv_file = CONTEXT["dotenv_path"]

    typer.confirm(
        "Are you sure you want to unset (remove) all configuration options in "
        f"{dotenv_file} file, deleting the file in the process?",
        abort=True,
    )

    if dotenv_file.exists():
        dotenv_file.unlink()
        print(f"Unset all configuration options. (Removed {dotenv_file}.)")
    else:
        print(f"{dotenv_file} file not found.")
