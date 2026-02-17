#!/usr/bin/env python3
"""
Check if Librarian server is running and healthy.

Usage:
    python check_server.py [--port 8000]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


def check_rest_api(port: int) -> dict | None:
    """Check if REST API is responding and return status."""
    try:
        url = f"http://localhost:{port}/api/v1/status"
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Check Librarian server status")
    parser.add_argument("--port", type=int, default=8000, help="REST API port")
    args = parser.parse_args()

    print("Checking Librarian server status...")
    print()

    status = check_rest_api(args.port)

    if status is None:
        print("[FAIL] REST API not responding on port", args.port)
        print()
        print("Start the server with:")
        print("  librarian serve")
        print()
        print("For MCP (Claude Desktop / OpenClaw):")
        print("  librarian mcp serve")
        return 1

    print(f"[OK] REST API responding (v{status.get('version', '?')})")
    print(f"  Uptime: {status.get('uptime_seconds', '?')}s")
    print()

    storage = status.get("storage", {})
    print(f"  Documents: {storage.get('total_documents', '?')}")
    print(f"  Chunks: {storage.get('total_chunks', '?')}")
    print(f"  DB size: {storage.get('sqlite_size_mb', '?')} MB")
    print()

    queue = status.get("queue", {})
    pending = queue.get("pending", 0)
    running = queue.get("running", 0)
    if pending or running:
        print(f"  Queue: {pending} pending, {running} running")
    else:
        print("  Queue: idle")

    print()
    print("[OK] Librarian server is healthy!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
