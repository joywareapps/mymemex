"""MCP resource handlers."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from ..storage.database import get_session
from .server import MyMemexContext


def register(mcp: FastMCP) -> None:
    """Register all MCP resources."""

    @mcp.resource("library://tags", name="All Tags", description="All tags with document counts")
    async def tags_resource() -> str:
        """List all tags with document counts."""
        async with get_session() as session:
            from ..services.tag import TagService

            service = TagService(session)
            tags = await service.list_tags()
            return json.dumps(
                [{"name": t["name"], "count": t["document_count"]} for t in tags],
                indent=2,
            )

    @mcp.resource(
        "library://stats", name="Library Statistics", description="Overall library statistics"
    )
    async def stats_resource() -> str:
        """Library overview statistics."""
        # Resources don't get Context injected, so we need config from somewhere.
        # Use the stashed config on the mcp instance.
        config = mcp._mymemex_config  # type: ignore[attr-defined]
        async with get_session() as session:
            from ..services.stats import StatsService

            service = StatsService(session, config)
            stats = await service.get_library_stats()
            return json.dumps(stats, indent=2, default=str)
