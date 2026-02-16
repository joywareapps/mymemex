"""CLI entry point for Librarian."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import AppConfig, load_config

app = typer.Typer(
    name="librarian",
    help="Sovereign document intelligence platform",
    add_completion=False,
)
console = Console()


@app.command()
def version():
    """Show version information."""
    console.print(f"Librarian v{__version__}")


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

        console.print(table)
    else:
        console.print("[yellow]Use --show to display current configuration[/]")


@app.command()
def init(
    path: Path = typer.Argument(
        Path("~/.local/share/librarian"),
        help="Directory to initialize",
    ),
):
    """Initialize a new Librarian instance."""
    path = path.expanduser()
    path.mkdir(parents=True, exist_ok=True)

    (path / "chromadb").mkdir(exist_ok=True)

    config_path = path / "config.yaml"
    if not config_path.exists():
        config_content = """\
# Librarian Configuration
debug: false
log_level: INFO

watch:
  directories:
    - /mnt/nas/documents  # Change to your document path
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
  path: ~/.local/share/librarian/librarian.db

server:
  host: 0.0.0.0
  port: 8000

ocr:
  enabled: false  # Enable for scanned documents (M5)
  language: eng
  dpi: 300

llm:
  provider: none  # Set to 'ollama' for AI features (M6+)
"""
        config_path.write_text(config_content)
        console.print(f"[green]Created:[/] {config_path}")

    console.print(f"[green]Initialized Librarian at:[/] {path}")
    console.print("\nNext steps:")
    console.print(f"  1. Edit {config_path}")
    console.print("  2. Run [cyan]librarian serve[/] to start the API server")


@app.command()
def serve(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
    host: str | None = typer.Option(None, "--host", help="Override host"),
    port: int | None = typer.Option(None, "--port", help="Override port"),
):
    """Start the Librarian API server."""
    import uvicorn

    cfg = load_config(config_path)
    if host:
        cfg.server.host = host
    if port:
        cfg.server.port = port

    from .app import create_app

    application = create_app(cfg)

    console.print(f"[green]Starting Librarian on {cfg.server.host}:{cfg.server.port}[/]")
    uvicorn.run(application, host=cfg.server.host, port=cfg.server.port, log_level="info")


def main():
    app()


if __name__ == "__main__":
    main()
