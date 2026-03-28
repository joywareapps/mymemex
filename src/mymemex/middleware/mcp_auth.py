"""ASGI middleware for MCP HTTP transport authentication."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import AppConfig


async def _send_response(send, status: int, body: str) -> None:
    body_bytes = body.encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body_bytes)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body_bytes})


class MCPAuthMiddleware:
    """
    Wraps the MCP HTTP app with token / IP-whitelist authentication.

    Mounted as an ASGI wrapper around the FastMCP streamable_http_app so it
    only applies to /mcp requests, not the rest of the FastAPI app.
    """

    def __init__(self, app, config: AppConfig) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope, receive, send) -> None:
        # Pass lifespan / websocket events through unchanged
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        from ..config import MCPAuthMode

        auth_mode = self.config.mcp.auth.mode

        if auth_mode == MCPAuthMode.none:
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}

        # IP whitelist check
        if auth_mode in (MCPAuthMode.ip_whitelist, MCPAuthMode.both):
            client = scope.get("client")
            client_ip = client[0] if client else None
            whitelist = self.config.mcp.auth.ip_whitelist
            if whitelist and client_ip not in whitelist:
                await _send_response(send, 403, json.dumps({"error": "IP not allowed"}))
                return

        # Bearer token check
        if auth_mode in (MCPAuthMode.token, MCPAuthMode.both):
            auth_header = headers.get(b"authorization", b"").decode()
            if not auth_header.startswith("Bearer "):
                await _send_response(
                    send, 401, json.dumps({"error": "Bearer token required"})
                )
                return
            token = auth_header[7:].strip()
            from ..storage.database import get_session
            from ..services.mcp_token import MCPTokenService

            async with get_session() as session:
                service = MCPTokenService(session)
                if not await service.validate(token):
                    await _send_response(
                        send, 401, json.dumps({"error": "Invalid or revoked token"})
                    )
                    return

        await self.app(scope, receive, send)
