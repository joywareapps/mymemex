"""Authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..services.auth import AuthService
from ..storage.database import get_session

router = APIRouter()


class LoginRequest(BaseModel):
    name: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    """Authenticate and receive a JWT access token."""
    config = request.app.state.config

    async with get_session() as session:
        user = await AuthService.authenticate(session, body.name, body.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    secret = config.auth.jwt_secret_key
    token = AuthService.create_access_token(
        user, secret=secret, expire_hours=config.auth.session_expiry_hours
    )

    # Also set as cookie for browser clients
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=config.auth.session_expiry_hours * 3600,
        samesite="lax",
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "name": user.name,
            "is_admin": user.is_admin,
        },
    )


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie("access_token")
    return {"detail": "Logged out"}


@router.get("/me")
async def me(request: Request):
    """Return current user info or auth status."""
    config = request.app.state.config

    if not config.auth.enabled:
        return {"authenticated": False, "auth_enabled": False}

    # Extract token from Authorization header or cookie
    token: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with get_session() as session:
        user = await AuthService.get_current_user(
            token=token,
            session=session,
            secret=config.auth.jwt_secret_key,
        )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "authenticated": True,
        "auth_enabled": True,
        "id": user.id,
        "name": user.name,
        "is_admin": user.is_admin,
    }
