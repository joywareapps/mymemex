"""CLI commands for user management."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

console = Console()

app = typer.Typer(help="User management")


def _run(coro):
    return asyncio.run(coro)


@app.command("create")
def create_user(
    name: str = typer.Argument(..., help="User name"),
    admin: bool = typer.Option(False, "--admin", help="Grant admin role"),
    default: bool = typer.Option(False, "--default", help="Mark as default user"),
    password: str | None = typer.Option(None, "--password", help="Set password"),
):
    """Create a new user."""
    async def _create():
        from ..config import load_config
        from ..services.auth import AuthService
        from ..storage.database import get_session, init_database

        config = load_config()
        await init_database(config.database.path)

        async with get_session() as session:
            from ..storage.repositories import UserRepository

            repo = UserRepository(session)
            password_hash = AuthService.hash_password(password) if password else None
            user = await repo.create(
                name=name,
                password_hash=password_hash,
                is_admin=admin,
                is_default=default,
            )
            return user

    user = _run(_create())
    console.print(f"[green]Created user:[/] {user.name} (ID: {user.id})")
    if admin:
        console.print("  [yellow]Role:[/] admin")
    if password:
        console.print("  [yellow]Password:[/] set")


@app.command("list")
def list_users():
    """List all users."""
    async def _list():
        from ..config import load_config
        from ..storage.database import get_session, init_database

        config = load_config()
        await init_database(config.database.path)

        async with get_session() as session:
            from ..storage.repositories import UserRepository

            repo = UserRepository(session)
            return await repo.list()

    users = _run(_list())

    if not users:
        console.print("[yellow]No users configured.[/]")
        return

    table = Table(title="Users")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Admin", style="yellow")
    table.add_column("Default", style="yellow")
    table.add_column("Has Password", style="yellow")
    table.add_column("Aliases")

    for user in users:
        aliases = json.loads(user.aliases or "[]")
        table.add_row(
            str(user.id),
            user.name,
            "✓" if user.is_admin else "",
            "✓" if user.is_default else "",
            "✓" if user.password_hash else "",
            ", ".join(aliases) if aliases else "",
        )

    console.print(table)
