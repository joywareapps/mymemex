"""MCP token generation and validation service."""

from __future__ import annotations

import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.models import MCPToken
from ..storage.repositories import MCPTokenRepository


class MCPTokenService:
    """Service for managing MCP API tokens."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MCPTokenRepository(session)

    @staticmethod
    def generate() -> tuple[str, str, str]:
        """
        Generate a new token.

        Returns:
            (full_token, token_prefix, token_hash)
        """
        random_part = secrets.token_urlsafe(24)
        full_token = f"mymemex_{random_part}"
        prefix = f"mymemex_{random_part[:8]}"
        token_hash = hashlib.sha256(full_token.encode()).hexdigest()
        return full_token, prefix, token_hash

    async def create(self, name: str) -> tuple[MCPToken, str]:
        """
        Create a new token record.

        Returns:
            (MCPToken record, full_token string — show once)
        """
        full_token, prefix, token_hash = self.generate()
        record = await self.repo.create(
            name=name, token_hash=token_hash, token_prefix=prefix
        )
        return record, full_token

    async def validate(self, token: str) -> MCPToken | None:
        """Validate a token; update last_used_at if valid."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = await self.repo.find_by_hash(token_hash)
        if record:
            await self.repo.update_last_used(record)
        return record

    async def list(self) -> list[MCPToken]:
        return await self.repo.list()

    async def revoke(self, token_id: int) -> bool:
        return await self.repo.revoke(token_id)
