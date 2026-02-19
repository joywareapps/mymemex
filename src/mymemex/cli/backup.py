"""Backup and restore commands."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tarfile
import tempfile
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


def _get_chromadb_path(config_path: Path | None = None) -> Path:
    """Derive ChromaDB directory from the configured database path."""
    db_path = _get_db_path(config_path)
    return db_path.parent / "chromadb"


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
        help="Backup name override (default: timestamp-based)",
    ),
) -> None:
    """Create a tar.gz backup of the database and vector store."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = name or f"mymemex-backup-{timestamp}.tar.gz"
    if not filename.endswith(".tar.gz"):
        filename += ".tar.gz"

    dest_dir = Path(destination)
    dest_dir.mkdir(parents=True, exist_ok=True)
    tar_path = dest_dir / filename

    console.print(f"[bold]Creating backup:[/] {tar_path}")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        includes: dict[str, bool] = {}

        # Backup SQLite database
        db_path = _get_db_path(config_path)
        if db_path.exists():
            dest_db = tmp / "mymemex.db"
            src = sqlite3.connect(str(db_path))
            dst = sqlite3.connect(str(dest_db))
            src.backup(dst)
            dst.close()
            src.close()
            includes["database"] = True
            db_size = dest_db.stat().st_size
            console.print(f"  [green]+[/] Database ({db_size / 1024:.0f} KB)")
        else:
            includes["database"] = False
            console.print(f"  [yellow]![/] Database not found at {db_path}")

        # Backup ChromaDB
        chroma_path = _get_chromadb_path(config_path)
        if chroma_path.exists() and chroma_path.is_dir():
            shutil.copytree(str(chroma_path), str(tmp / "chromadb"))
            includes["vectors"] = True
            console.print("  [green]+[/] Vector store")
        else:
            includes["vectors"] = False

        # Write metadata
        doc_count = 0
        if includes.get("database"):
            try:
                conn = sqlite3.connect(str(tmp / "mymemex.db"))
                row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
                doc_count = row[0] if row else 0
                conn.close()
            except Exception:
                pass

        metadata = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "document_count": doc_count,
            "includes": includes,
        }
        (tmp / "metadata.json").write_text(json.dumps(metadata, indent=2))

        # Pack into tar.gz
        with tarfile.open(str(tar_path), "w:gz") as tar:
            tar.add(str(tmp), arcname=".")

    size_kb = tar_path.stat().st_size / 1024
    console.print(f"[green]Backup created:[/] {tar_path} ({size_kb:.0f} KB)")


@app.command()
def restore(
    backup_path: Path = typer.Argument(
        ...,
        help="Path to .tar.gz backup file",
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Config file path",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Restore from a .tar.gz backup."""
    backup_path = Path(backup_path)

    if not backup_path.exists():
        console.print(f"[red]Error:[/] Backup file not found: {backup_path}")
        raise typer.Exit(1)

    # Validate
    try:
        with tarfile.open(str(backup_path), "r:gz") as tar:
            names = tar.getnames()
        has_metadata = "metadata.json" in names or "./metadata.json" in names
        if not has_metadata:
            console.print("[red]Error:[/] Invalid backup (missing metadata.json)")
            raise typer.Exit(1)
    except tarfile.TarError as e:
        console.print(f"[red]Error:[/] Not a valid tar.gz file: {e}")
        raise typer.Exit(1)

    db_path = _get_db_path(config_path)
    chroma_dest = _get_chromadb_path(config_path)

    console.print(f"[bold]Restoring from:[/] {backup_path}")
    console.print(f"  Database → {db_path}")
    console.print(f"  Vector store → {chroma_dest}")

    if not yes:
        confirm = typer.confirm("This will overwrite existing data. Continue?")
        if not confirm:
            raise typer.Abort()

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        with tarfile.open(str(backup_path), "r:gz") as tar:
            tar.extractall(str(tmp))

        # Restore database
        backup_db = tmp / "mymemex.db"
        if backup_db.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(backup_db), str(db_path))
            console.print(f"  [green]+[/] Database restored to {db_path}")
        else:
            console.print("  [yellow]![/] No database in backup")

        # Restore ChromaDB
        backup_chroma = tmp / "chromadb"
        if backup_chroma.exists():
            if chroma_dest.exists():
                shutil.rmtree(str(chroma_dest))
            shutil.copytree(str(backup_chroma), str(chroma_dest))
            console.print(f"  [green]+[/] Vector store restored to {chroma_dest}")

    console.print("[green]Restore complete.[/] Please restart the server.")


@app.command("list")
def list_backups(
    destination: Path = typer.Option(
        "./backups",
        "--destination", "-d",
        help="Backup directory to list",
    ),
) -> None:
    """List available .tar.gz backups."""
    destination = Path(destination)

    if not destination.exists():
        console.print("[yellow]No backups found[/]")
        return

    backups = sorted(
        [f for f in destination.iterdir() if f.is_file() and f.name.endswith(".tar.gz")],
        reverse=True,
    )

    if not backups:
        console.print("[yellow]No backups found[/]")
        return

    table = Table(title=f"Backups in {destination}")
    table.add_column("Filename", style="cyan")
    table.add_column("Size", style="green")
    table.add_column("Created", style="yellow")

    for backup_file in backups:
        size_kb = backup_file.stat().st_size / 1024
        size_str = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"

        # Try to read metadata from archive
        created = "unknown"
        try:
            with tarfile.open(str(backup_file), "r:gz") as tar:
                for meta_name in ("metadata.json", "./metadata.json"):
                    try:
                        f = tar.extractfile(meta_name)
                        if f:
                            meta = json.loads(f.read().decode())
                            created = meta.get("created", "unknown")
                            break
                    except KeyError:
                        continue
        except Exception:
            pass

        table.add_row(backup_file.name, size_str, created)

    console.print(table)
