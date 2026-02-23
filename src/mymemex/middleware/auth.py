"""Middleware to attach auth context and enforce authentication on protected paths."""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..services.auth import AuthService
from ..storage.database import get_session


class AuthMiddleware(BaseHTTPMiddleware):
    """Attach auth context to every request. Enforce auth on protected paths."""

    EXEMPT_PATHS = {"/api/v1/admin/setup/status", "/ui/login"}

    async def dispatch(self, request: Request, call_next):
        config = request.app.state.config

        # Extract token from Bearer header or cookie
        token = request.cookies.get("access_token")
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # Attach context to request.state (templates access via `request`)
        request.state.auth_enabled = config.auth.enabled
        request.state.current_user = None

        if config.auth.enabled and token:
            async with get_session() as session:
                user = await AuthService.get_current_user(
                    token, session, config.auth.jwt_secret_key
                )
            if user:
                request.state.current_user = {
                    "id": user.id,
                    "name": user.name,
                    "is_admin": user.is_admin,
                }

        # No enforcement when auth disabled
        if not config.auth.enabled:
            return await call_next(request)

        path = request.url.path
        method = request.method

        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        needs_auth = (
            path.startswith("/api/v1/admin/")
            or path.startswith("/ui/admin/")
            or (path.startswith("/api/v1/documents") and method in ("POST", "PATCH", "DELETE"))
            or (path.startswith("/api/v1/tags") and method in ("POST", "DELETE"))
        )

        if needs_auth and not request.state.current_user:
            if path.startswith("/ui/"):
                return Response(
                    status_code=302,
                    headers={"Location": f"/ui/login?next={path}"},
                )
            return Response(
                content='{"detail":"Authentication required"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)
