from __future__ import annotations

import typer

from schemaform.app import create_app
from schemaform.config import Settings

cli = typer.Typer(add_completion=False)


@cli.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    host: str | None = typer.Option(None, help="バインドするアドレス"),
    port: int | None = typer.Option(None, help="バインドするポート"),
) -> None:
    ctx.obj = {"host": host, "port": port}
    if ctx.invoked_subcommand is None:
        run_server(host, port)


@cli.command()
def run(
    ctx: typer.Context,
    host: str | None = typer.Option(None, help="バインドするアドレス"),
    port: int | None = typer.Option(None, help="バインドするポート"),
) -> None:
    base = ctx.obj or {}
    resolved_host = host or base.get("host")
    resolved_port = port if port is not None else base.get("port")
    run_server(resolved_host, resolved_port)


def run_server(host: str | None, port: int | None) -> None:
    import uvicorn

    settings = Settings()
    app = create_app(settings)
    resolved_host = host or settings.host
    resolved_port = port if port is not None else settings.port
    uvicorn.run(app, host=resolved_host, port=resolved_port)
