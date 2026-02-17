#!/usr/bin/env python3
"""
Test MCP connection to Librarian by verifying tool registration.

Usage:
    python test_connection.py
"""

import sys


EXPECTED_TOOLS = [
    "search_documents",
    "get_document",
    "get_document_text",
    "list_documents",
    "add_tag",
    "remove_tag",
    "upload_document",
    "get_library_stats",
]

EXPECTED_RESOURCES = [
    "library://tags",
    "library://stats",
]

EXPECTED_PROMPTS = [
    "search_and_summarize",
    "compare_documents",
]


def main():
    print("Testing Librarian MCP server registration...")
    print()

    try:
        from librarian.config import load_config
        from librarian.mcp import create_mcp_server
    except ImportError:
        print("[FAIL] Librarian not installed")
        print("  Install with: pip install librarian")
        return 1

    config = load_config()
    mcp = create_mcp_server(config)

    # Check tools
    print("Tools:")
    tool_manager = mcp._tool_manager
    registered_tools = set(tool_manager._tools.keys())

    all_ok = True
    for tool in EXPECTED_TOOLS:
        if tool in registered_tools:
            print(f"  [OK] {tool}")
        else:
            print(f"  [MISSING] {tool}")
            all_ok = False

    print()
    print("Resources:")
    resource_manager = mcp._resource_manager
    registered_resources = set(resource_manager._resources.keys())

    for uri in EXPECTED_RESOURCES:
        if uri in registered_resources:
            print(f"  [OK] {uri}")
        else:
            print(f"  [MISSING] {uri}")
            all_ok = False

    print()
    print("Prompts:")
    prompt_manager = mcp._prompt_manager
    registered_prompts = set(prompt_manager._prompts.keys())

    for prompt in EXPECTED_PROMPTS:
        if prompt in registered_prompts:
            print(f"  [OK] {prompt}")
        else:
            print(f"  [MISSING] {prompt}")
            all_ok = False

    print()
    if all_ok:
        print("[OK] All MCP tools, resources, and prompts registered!")
        return 0
    else:
        print("[FAIL] Some components missing")
        return 1


if __name__ == "__main__":
    sys.exit(main())
