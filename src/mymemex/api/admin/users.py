"""Admin user CRUD endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...services.auth import AuthService
from ...storage.database import get_session
from ...storage.repositories import UserRepository

router = APIRouter()


class UserCreate(BaseModel):
    name: str
    aliases: list[str] = []
    password: str | None = None    # Plaintext — hashed before storage
    is_admin: bool = False
    is_default: bool = False


class UserUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    password: str | None = None    # Set new password
    is_admin: bool | None = None
    is_default: bool | None = None


def _user_to_dict(user) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "aliases": json.loads(user.aliases or "[]"),
        "is_admin": user.is_admin,
        "is_default": user.is_default,
        "has_password": user.password_hash is not None,
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
        password_hash = AuthService.hash_password(body.password) if body.password else None
        user = await repo.create(
            name=body.name,
            aliases=json.dumps(body.aliases),
            password_hash=password_hash,
            is_admin=body.is_admin,
            is_default=body.is_default,
        )
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
        if body.password is not None:
            kwargs["password_hash"] = AuthService.hash_password(body.password)
        if body.is_admin is not None:
            kwargs["is_admin"] = body.is_admin
        if body.is_default is not None:
            kwargs["is_default"] = body.is_default
        await repo.update(user, **kwargs)
    return _user_to_dict(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    async with get_session() as session:
        repo = UserRepository(session)
        deleted = await repo.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
