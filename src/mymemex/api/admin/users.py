"""Admin user CRUD endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...storage.database import get_session
from ...storage.repositories import UserRepository

router = APIRouter()


class UserCreate(BaseModel):
    name: str
    aliases: list[str] = []


class UserUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None


def _user_to_dict(user) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "aliases": json.loads(user.aliases or "[]"),
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.get("/users")
async def list_users():
    async with get_session() as session:
        repo = UserRepository(session)
        users = await repo.list()
    return {"users": [_user_to_dict(u) for u in users]}


@router.post("/users", status_code=201)
async def create_user(body: UserCreate):
    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.create(name=body.name, aliases=json.dumps(body.aliases))
    return _user_to_dict(user)


@router.get("/users/{user_id}")
async def get_user(user_id: int):
    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.patch("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate):
    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        kwargs = {}
        if body.name is not None:
            kwargs["name"] = body.name
        if body.aliases is not None:
            kwargs["aliases"] = json.dumps(body.aliases)
        await repo.update(user, **kwargs)
    return _user_to_dict(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    async with get_session() as session:
        repo = UserRepository(session)
        deleted = await repo.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
