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
    rich_markup_mode="rich",
)

# Add sub-Typer apps (sub-command groups)
for typer_app, typer_app_kwargs in get_subtyper_apps():
    APP.add_typer(typer_app, **typer_app_kwargs)

@APP.command(name="list")
def list_entities(
    namespace: OptionalStr = typer.Option(
        str(CONFIG.base_url).rstrip("/"),
        "--namespace",
        "-n",
        help="Namespace to list entities from.",
        show_default=True,
    )
) -> None:
    """List entities from the entities service."""
    if namespace is None:
        namespace = str(CONFIG.base_url).rstrip("/")

    namespace_as_url: AnyHttpUrl | None = None
    with contextlib.suppress(ValidationError):
        namespace_as_url = AnyHttpUrl(namespace)

    if namespace_as_url is not None:
        # Validate namespace and retrieve the specific namespace (if any)
        if (match := URI_REGEX.match(str(namespace_as_url))) is None:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Namespace {namespace_as_url} does not "
                "match the URI regex."
            )
            raise typer.Exit(1)

        # Replace the namespace with the specific namespace
        # This will be `None` if the namespace is the "core" namespace
        namespace = match.group("specific_namespace")

    # Namespace is now the specific namespace (str) or the "core" namespace (None)
    path_prefix = f"/{namespace}" if namespace is not None else ""

    with httpx.Client(base_url=str(CONFIG.base_url)) as client:
        try:
            response = client.get(
                f"{path_prefix}/_api/entities",
                params={"namespace": namespace},
            )
        except httpx.HTTPError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not list entities. HTTP exception: "
                f"{exc}"
            )
            raise typer.Exit(1) from exc

    if not response.is_success:
        try:
            error_message = response.json()
        except json.JSONDecodeError as exc:
            ERROR_CONSOLE.print(
                f"[bold red]Error[/bold red]: Could not list entities. JSON decode "
                f"error: {exc}"
            )
            raise typer.Exit(1) from exc

        ERROR_CONSOLE.print(
            f"[bold red]Error[/bold red]: Could not list entities. HTTP status code: "
            f"{response.status_code}. Error response: "
        )
        ERROR_CONSOLE.print_json(data=error_message)
        raise typer.Exit(1)

    # We do not need to validate the response, since the server's response model will do
    # that for us
    entities: list[Entity] = [soft_entity(**entity) for entity in response.json()]

    if not entities:
        print(f"No entities found in namespace {namespace}")
        raise typer.Exit()

    # Print entities
    table = Table(
        title=f"Entities in namespace {namespace}:",
        title_style="bold",
        title_justify="left",
        box=box.SIMPLE_HEAD,
        highlight=True,
    )

    table.add_column("Name", no_wrap=True)
    table.add_column("Version", no_wrap=True)

    previous_entity_name = ""
    for entity in sorted(entities, key=lambda entity: entity.name):
        if entity.name == previous_entity_name:
            # Only add the version
            table.add_row("", entity.version)
        else:
            table.add_row(entity.name, entity.version)

        previous_entity_name = entity.name

    print("", table)

# Add all "leaf"-commands
for command, commands_kwargs in get_commands():
    APP.command(**commands_kwargs)(command)
