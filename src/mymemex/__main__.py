"""CLI entry point for MyMemex."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import AppConfig, load_config

app = typer.Typer(
    name="mymemex",
    help="Sovereign document intelligence platform",
    add_completion=False,
)
console = Console()


@app.command()
def version():
    """Show version information."""
    console.print(f"MyMemex v{__version__}")


@app.command("config")
def show_config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    path: Path | None = typer.Option(None, "--path", "-p", help="Config file path"),
):
    """Manage configuration."""
    cfg = load_config(path)

    if show:
        table = Table(title="Configuration")
        table.add_column("Section", style="cyan")
        table.add_column("Key", style="green")
        table.add_column("Value", style="yellow")

        def add_section(section_name: str, obj: BaseModel):
            for field_name in type(obj).model_fields:
                value = getattr(obj, field_name)
                if isinstance(value, BaseModel):
                    continue
                if isinstance(value, Path):
                    value = str(value)
                elif isinstance(value, list):
                    value = ", ".join(map(str, value)) if value else "(empty)"
                table.add_row(section_name, field_name, str(value))

        add_section("core", cfg)
        add_section("watch", cfg.watch)
        add_section("database", cfg.database)
        add_section("server", cfg.server)
        add_section("ocr", cfg.ocr)
        add_section("llm", cfg.llm)
        add_section("ai", cfg.ai)

        console.print(table)
    else:
        console.print("[yellow]Use --show to display current configuration[/]")


@app.command()
def init(
    path: Path = typer.Argument(
        Path("./data"),
        help="Directory to initialize",
    ),
):
    """Initialize a new MyMemex instance."""
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)

    config_path = path.parent / "config.yaml"
    if not config_path.exists():
        config_content = f"""\
# MyMemex Configuration
debug: false
log_level: INFO

watch:
  # Add watch folders via the admin UI after starting the server.
  file_patterns:
    - "*.pdf"
    - "*.png"
    - "*.jpg"
    - "*.jpeg"
  ignore_patterns:
    - "*/.*"
    - "*/.Trash-*"
    - "*/@eaDir/*"
  debounce_seconds: 2.0
  max_file_size_mb: 100

database:
  path: {path}/mymemex.db

server:
  host: 0.0.0.0
  port: 8000

ocr:
  enabled: false  # Enable for scanned documents
  language: eng
  dpi: 300

llm:
  provider: none  # Set to 'ollama' for AI features

ai:
  semantic_search_enabled: false
  embedding_model: nomic-embed-text
  embedding_batch_size: 8
"""
        config_path.write_text(config_content)
        console.print(f"[green]Created:[/] {config_path}")

    console.print(f"[green]Initialized MyMemex at:[/] {path}")
    console.print("\nNext steps:")
    console.print(f"  1. Edit {config_path}")
    console.print("  2. Run [cyan]mymemex serve[/] to start the API server")


@app.command()
def serve(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
    host: str | None = typer.Option(None, "--host", help="Override host"),
    port: int | None = typer.Option(None, "--port", help="Override port"),
):
    """Start the MyMemex API server."""
    import uvicorn

    cfg = load_config(config_path)
    if host:
        cfg.server.host = host
    if port:
        cfg.server.port = port

    from .app import create_app

    application = create_app(cfg)

    console.print(f"[green]Starting MyMemex on {cfg.server.host}:{cfg.server.port}[/]")
    uvicorn.run(application, host=cfg.server.host, port=cfg.server.port, log_level="info")


# --- Backup command group ---

from .cli.backup import app as backup_app

app.add_typer(backup_app, name="backup")


# --- Users command group ---

from .cli.users import app as users_app

app.add_typer(users_app, name="users")


# --- MCP command group ---

mcp_app = typer.Typer(help="MCP server commands")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("serve")
def mcp_serve(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """Start the MCP server (stdio transport for Claude Desktop)."""
    cfg = load_config(config_path)

    from .mcp import create_mcp_server

    mcp_server = create_mcp_server(cfg)
    mcp_server.run(transport="stdio")


def main():
    app()


if __name__ == "__main__":
    main()
