"""Backup and restore commands."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..config import load_config

app = typer.Typer(help="Backup and restore database")
console = Console()


def _get_db_path(config_path: Path | None = None) -> Path:
    """Resolve the database path from config."""
    cfg = load_config(config_path)
    return cfg.database.path


def _get_chromadb_path() -> Path | None:
    """Find ChromaDB directory if it exists."""
    candidates = [
        Path.home() / ".local" / "share" / "librarian" / "chromadb",
        Path.cwd() / "chromadb",
    ]
    for p in candidates:
        if p.exists() and p.is_dir():
            return p
    return None


@app.command()
def create(
    destination: Path = typer.Option(
        "./backups",
        "--destination", "-d",
        help="Backup destination directory",
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Config file path",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name", "-n",
        help="Backup name (default: timestamp)",
    ),
) -> None:
    """Create a backup of the database and vector store."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = name or f"librarian_backup_{timestamp}"
    backup_dir = Path(destination) / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Creating backup:[/] {backup_dir}")

    # Backup SQLite database
    db_path = _get_db_path(config_path)
    if db_path.exists():
        dest_db = backup_dir / "librarian.db"
        # Use SQLite online backup API for consistency
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(dest_db))
        src.backup(dst)
        dst.close()
        src.close()
        db_size = dest_db.stat().st_size
        console.print(f"  [green]+[/] Database ({db_size / 1024:.0f} KB)")
    else:
        console.print(f"  [yellow]![/] Database not found at {db_path}")

    # Backup ChromaDB if exists
    chroma_path = _get_chromadb_path()
    has_vectors = False
    if chroma_path:
        dest_chroma = backup_dir / "chromadb"
        shutil.copytree(chroma_path, dest_chroma)
        has_vectors = True
        console.print(f"  [green]+[/] Vector store")

    # Write manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "version": "1.0",
        "includes": {
            "database": db_path.exists(),
            "vectors": has_vectors,
        },
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    console.print(f"[green]Backup created:[/] {backup_dir}")


@app.command()
def restore(
    backup_path: Path = typer.Argument(
        ...,
        help="Path to backup directory",
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Config file path",
    ),
) -> None:
    """Restore from a backup."""
    backup_path = Path(backup_path)

    manifest_path = backup_path / "manifest.json"
    if not manifest_path.exists():
        console.print("[red]Error:[/] Invalid backup (no manifest.json)")
        raise typer.Exit(1)

    manifest = json.loads(manifest_path.read_text())
    console.print(f"[bold]Restoring from:[/] {backup_path}")
    console.print(f"  Created: {manifest.get('created_at', 'unknown')}")

    # Restore database
    backup_db = backup_path / "librarian.db"
    if backup_db.exists():
        db_path = _get_db_path(config_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(backup_db), str(db_path))
        console.print(f"  [green]+[/] Database restored to {db_path}")
    else:
        console.print("  [yellow]![/] No database in backup")

    # Restore ChromaDB
    backup_chroma = backup_path / "chromadb"
    if backup_chroma.exists():
        chroma_dest = _get_chromadb_path()
        if chroma_dest is None:
            chroma_dest = Path.home() / ".local" / "share" / "librarian" / "chromadb"
        if chroma_dest.exists():
            shutil.rmtree(chroma_dest)
        shutil.copytree(backup_chroma, chroma_dest)
        console.print(f"  [green]+[/] Vector store restored to {chroma_dest}")

    console.print("[green]Restore complete[/]")


@app.command("list")
def list_backups(
    destination: Path = typer.Option(
        "./backups",
        "--destination", "-d",
        help="Backup directory to list",
    ),
) -> None:
    """List available backups."""
    destination = Path(destination)

    if not destination.exists():
        console.print("[yellow]No backups found[/]")
        return

    backups = sorted(
        [d for d in destination.iterdir() if d.is_dir()],
        reverse=True,
    )

    if not backups:
        console.print("[yellow]No backups found[/]")
        return

    table = Table(title=f"Backups in {destination}")
    table.add_column("Name", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Contents", style="yellow")

    for backup in backups:
        manifest_path = backup / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            created = manifest.get("created_at", "unknown")
            includes = manifest.get("includes", {})
            parts = []
            if includes.get("database"):
                parts.append("db")
            if includes.get("vectors"):
                parts.append("vectors")
            table.add_row(backup.name, created, ", ".join(parts) or "empty")
        else:
            table.add_row(backup.name, "?", "invalid")

    console.print(table)
