"""Admin MCP token management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...storage.database import get_session
from ...storage.repositories import MCPTokenRepository

router = APIRouter()


class TokenCreate(BaseModel):
    name: str


def _token_to_dict(token, include_full: bool = False) -> dict:
    d = {
        "id": token.id,
        "name": token.name,
        "token_prefix": token.token_prefix,
        "is_active": token.is_active,
        "created_at": token.created_at.isoformat(),
        "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
    }
    return d


@router.get("/mcp/tokens")
async def list_tokens():
    async with get_session() as session:
        repo = MCPTokenRepository(session)
        tokens = await repo.list()
    return {"tokens": [_token_to_dict(t) for t in tokens]}


@router.post("/mcp/tokens", status_code=201)
async def create_token(body: TokenCreate):
    from ...services.mcp_token import MCPTokenService

    async with get_session() as session:
        service = MCPTokenService(session)
        token_record, full_token = await service.create(body.name)

    # Return full token ONCE (not stored)
    result = _token_to_dict(token_record)
    result["token"] = full_token
    return result


@router.delete("/mcp/tokens/{token_id}", status_code=204)
async def revoke_token(token_id: int):
    async with get_session() as session:
        repo = MCPTokenRepository(session)
        revoked = await repo.revoke(token_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Token not found")
