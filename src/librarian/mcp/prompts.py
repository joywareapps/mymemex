"""MCP prompt templates."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import UserMessage


def register(mcp: FastMCP) -> None:
    """Register all MCP prompts."""

    @mcp.prompt()
    async def search_and_summarize(query: str) -> list[UserMessage]:
        """Search the library and summarize key findings.

        Args:
            query: The search query.
        """
        return [
            UserMessage(
                content=(
                    f'Search the library for "{query}" and summarize the key findings.\n'
                    "\n"
                    "Focus on:\n"
                    "- Main topics covered\n"
                    "- Document types found\n"
                    "- Any notable patterns or outliers\n"
                    "\n"
                    "Cite specific documents when relevant."
                )
            )
        ]

    @mcp.prompt()
    async def compare_documents(document_ids: str) -> list[UserMessage]:
        """Compare two or more documents.

        Args:
            document_ids: Comma-separated document IDs to compare.
        """
        return [
            UserMessage(
                content=(
                    f"Compare the following documents:\n"
                    f"- Document IDs: {document_ids}\n"
                    "\n"
                    "Analyze:\n"
                    "- Key similarities\n"
                    "- Important differences\n"
                    "- Temporal changes (if applicable)\n"
                    "- Recommendations"
                )
            )
        ]
