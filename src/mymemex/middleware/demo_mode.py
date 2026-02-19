"""Middleware to block write operations in demo mode."""

from __future__ import annotations

import os
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class DemoModeMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks POST, PATCH, and DELETE operations
    when the DEMO_MODE environment variable is set to "true".
    """

    def is_write_operation(self, path: str) -> bool:
        """Check if the path corresponds to a blocked write operation."""
        # Blocked API endpoints
        blocked_prefixes = [
            "/api/v1/documents/upload",
            "/api/v1/documents/", # PATCH/DELETE on documents
            "/api/v1/tags/",      # DELETE on tags
            "/api/v1/admin/config",
            "/api/v1/admin/watch-folders",
            "/api/v1/admin/backup/",
            "/api/v1/admin/mcp/tokens",
            "/api/v1/admin/users",
            "/api/v1/admin/queue/",
        ]
        
        # Exact matches for document detail patch/delete
        # (covered by /api/v1/documents/ prefix but being explicit)
        
        for prefix in blocked_prefixes:
            if path.startswith(prefix):
                # Special cases: GET operations on these prefixes should be allowed
                # This middleware only checks method in dispatch
                return True
        return False

    async def dispatch(self, request: Request, call_next):
        if os.environ.get("DEMO_MODE") == "true":
            if request.method in ("POST", "PATCH", "DELETE", "PUT"):
                if self.is_write_operation(request.url.path):
                    # For API requests, return JSON
                    if request.url.path.startswith("/api/"):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Demo mode: write operations are disabled"}
                        )
                    # For others (if any), return plain text
                    return Response("Demo mode: write operations are disabled", status_code=403)
        
        return await call_next(request)
