"""Authentication service — password hashing, JWT tokens, user lookup."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.repositories import UserRepository

if TYPE_CHECKING:
    from ..storage.models import User

log = structlog.get_logger()


class AuthService:
    """Authentication utilities."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password with bcrypt."""
        import bcrypt

        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verify a plaintext password against a bcrypt hash."""
        import bcrypt

        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    async def authenticate(session: AsyncSession, name: str, password: str) -> User | None:
        """
        Authenticate a user by name and password.

        Returns the User if credentials are valid, None otherwise.
        """
        repo = UserRepository(session)
        user = await repo.get_by_name(name)
        if not user:
            return None
        if not user.password_hash:
            # User has no password set — authentication always fails
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_access_token(user: User, secret: str, expire_hours: int = 24) -> str:
        """Create a JWT access token for the user."""
        from jose import jwt

        if not secret:
            secret = secrets.token_hex(32)

        expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
        payload = {
            "sub": str(user.id),
            "name": user.name,
            "is_admin": user.is_admin,
            "exp": expire,
        }
        return jwt.encode(payload, secret, algorithm="HS256")

    @staticmethod
    def decode_token(token: str, secret: str) -> dict | None:
        """
        Decode and validate a JWT token.

        Returns the payload dict, or None if invalid/expired.
        """
        from jose import JWTError, jwt

        if not secret:
            return None
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload
        except JWTError:
            return None

    @staticmethod
    async def get_current_user(
        token: str | None,
        session: AsyncSession,
        secret: str,
    ) -> User | None:
        """
        Resolve a JWT token to a User.

        Returns None if token is missing or invalid.
        """
        if not token:
            return None

        payload = AuthService.decode_token(token, secret)
        if not payload:
            return None

        user_id_str = payload.get("sub")
        if not user_id_str:
            return None

        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return None

        repo = UserRepository(session)
        return await repo.get(user_id)
