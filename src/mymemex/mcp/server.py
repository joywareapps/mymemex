"""MyMemex MCP Server — main setup and lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from ..config import AppConfig, load_config
from ..storage.database import init_database


@dataclass
class MyMemexContext:
    """Lifespan context available to all MCP handlers."""

    config: AppConfig


@asynccontextmanager
async def lifespan(server: FastMCP[MyMemexContext]):
    """Initialize database and yield config for tool handlers."""
    config = server._mymemex_config  # type: ignore[attr-defined]
    await init_database(config.database.path)
    yield MyMemexContext(config=config)


def create_mcp_server(config: AppConfig | None = None) -> FastMCP[MyMemexContext]:
    """Create and configure the MCP server."""
    import os
    if os.environ.get("DEMO_MODE") == "true":
        raise RuntimeError("MCP server is disabled in demo mode")

    if config is None:
        config = load_config()

    mcp = FastMCP(
        "mymemex",
        instructions=(
            "MyMemex is a document intelligence platform. "
            "Use the available tools to search, browse, and manage documents."
        ),
        lifespan=lifespan,
    )

    # Stash config so lifespan can access it
    mcp._mymemex_config = config  # type: ignore[attr-defined]

    # Register tools, resources, and prompts
    from . import prompts, resources, tools

    tools.register(mcp)
    resources.register(mcp)
    prompts.register(mcp)

    return mcp
