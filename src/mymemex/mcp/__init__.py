"""MCP server — exposes MyMemex via Model Context Protocol."""

from .server import create_mcp_server

__all__ = ["create_mcp_server"]
