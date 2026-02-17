#!/usr/bin/env python3
"""
Quick CLI search utility for Librarian.

Usage:
    python quick_search.py "insurance policy"
    python quick_search.py --mode keyword "tax documents"
    python quick_search.py --limit 5 "medical"
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def search(query: str, mode: str = "keyword", limit: int = 10, port: int = 8000):
    """Search documents via REST API."""
    params = urllib.parse.urlencode({"q": query, "limit": limit})

    if mode == "keyword":
        url = f"http://localhost:{port}/api/v1/search/keyword?{params}"
    elif mode == "semantic":
        url = f"http://localhost:{port}/api/v1/search/semantic?{params}"
    else:
        url = f"http://localhost:{port}/api/v1/search/hybrid?{params}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        print(f"[FAIL] Could not connect to Librarian REST API: {e}")
        print(f"  Make sure the server is running: librarian serve")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Quick search Librarian documents")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--mode",
        choices=["keyword", "semantic", "hybrid"],
        default="keyword",
        help="Search mode (default: keyword)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--port", type=int, default=8000, help="REST API port")
    args = parser.parse_args()

    print(f"Searching for: {args.query}")
    print(f"Mode: {args.mode}")
    print()

    data = search(args.query, args.mode, args.limit, args.port)
    results = data.get("results", [])

    if not results:
        print("No results found.")
        return 0

    total = data.get("total", len(results))
    print(f"Found {total} results:\n")

    for i, result in enumerate(results, 1):
        title = result.get("title") or result.get("original_filename", "Untitled")
        doc_id = result.get("document_id", "?")

        # Different result shapes per search mode
        score = result.get("score") or result.get("rank") or result.get("distance", 0)
        text = result.get("snippet") or result.get("text", "")

        print(f"{i}. {title}")
        print(f"   ID: {doc_id} | Score: {score}")
        if text:
            # Strip markup from snippet
            clean = text.replace("<mark>", "").replace("</mark>", "")
            print(f"   {clean[:120]}...")
        tags = result.get("tags", [])
        if tags:
            print(f"   Tags: {', '.join(tags)}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
