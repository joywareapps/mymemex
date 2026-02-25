"""Admin routing rules CRUD endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.queue import TaskQueue, TaskType
from ...storage.database import get_session
from ...storage.repositories import RoutingRuleRepository, WatchDirectoryRepository
from ...services.routing import _has_pending_route_task

router = APIRouter(prefix="/routing-rules")


class RoutingRuleCreate(BaseModel):
    watch_directory_id: int
    name: str
    directory_name: str
    tags: list[str] = []
    match_mode: str = "any"
    priority: int = 100
    sub_levels: list[str] = []
    is_active: bool = True


class RoutingRuleUpdate(BaseModel):
    name: str | None = None
    directory_name: str | None = None
    tags: list[str] | None = None
    match_mode: str | None = None
    priority: int | None = None
    sub_levels: list[str] | None = None
    is_active: bool | None = None


def _rule_to_dict(rule) -> dict:
    return {
        "id": rule.id,
        "watch_directory_id": rule.watch_directory_id,
        "name": rule.name,
        "directory_name": rule.directory_name,
        "tags": json.loads(rule.tags or "[]"),
        "match_mode": rule.match_mode,
        "priority": rule.priority,
        "sub_levels": json.loads(rule.sub_levels or "[]"),
        "is_active": rule.is_active,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


async def _enqueue_reroute_all(watch_directory_id: int) -> dict:
    """Enqueue ROUTE_FILE for all documents in a watch directory. Returns stats."""
    async with get_session() as session:
        rule_repo = RoutingRuleRepository(session)
        doc_ids = await rule_repo.list_doc_ids_for_watch_dir(watch_directory_id)
        queue = TaskQueue(session)
        enqueued = 0
        for doc_id in doc_ids:
            if not await _has_pending_route_task(session, doc_id):
                await queue.enqueue(
                    TaskType.ROUTE_FILE,
                    {"document_id": doc_id},
                    document_id=doc_id,
                    priority=1,
                )
                enqueued += 1
    return {"enqueued": enqueued, "total_documents": len(doc_ids)}


@router.get("")
async def list_routing_rules(watch_directory_id: int | None = None):
    async with get_session() as session:
        repo = RoutingRuleRepository(session)
        rules = await repo.list_all(watch_directory_id=watch_directory_id)
    return {"rules": [_rule_to_dict(r) for r in rules]}


@router.post("", status_code=201)
async def create_routing_rule(body: RoutingRuleCreate):
    async with get_session() as session:
        wd_repo = WatchDirectoryRepository(session)
        wd = await wd_repo.get(body.watch_directory_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch directory not found")

        repo = RoutingRuleRepository(session)
        rule = await repo.create(
            watch_directory_id=body.watch_directory_id,
            name=body.name,
            directory_name=body.directory_name,
            tags=json.dumps(body.tags),
            match_mode=body.match_mode,
            priority=body.priority,
            sub_levels=json.dumps(body.sub_levels),
            is_active=body.is_active,
        )
        result = _rule_to_dict(rule)

    await _enqueue_reroute_all(body.watch_directory_id)
    return result


@router.get("/{rule_id}")
async def get_routing_rule(rule_id: int):
    async with get_session() as session:
        repo = RoutingRuleRepository(session)
        rule = await repo.get(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")
    return _rule_to_dict(rule)


@router.patch("/{rule_id}")
async def update_routing_rule(rule_id: int, body: RoutingRuleUpdate):
    async with get_session() as session:
        repo = RoutingRuleRepository(session)
        rule = await repo.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Routing rule not found")

        watch_directory_id = rule.watch_directory_id
        kwargs: dict = {}
        if body.name is not None:
            kwargs["name"] = body.name
        if body.directory_name is not None:
            kwargs["directory_name"] = body.directory_name
        if body.tags is not None:
            kwargs["tags"] = json.dumps(body.tags)
        if body.match_mode is not None:
            kwargs["match_mode"] = body.match_mode
        if body.priority is not None:
            kwargs["priority"] = body.priority
        if body.sub_levels is not None:
            kwargs["sub_levels"] = json.dumps(body.sub_levels)
        if body.is_active is not None:
            kwargs["is_active"] = body.is_active

        if kwargs:
            await repo.update(rule, **kwargs)
        result = _rule_to_dict(rule)

    await _enqueue_reroute_all(watch_directory_id)
    return result


@router.delete("/{rule_id}", status_code=204)
async def delete_routing_rule(rule_id: int):
    async with get_session() as session:
        repo = RoutingRuleRepository(session)
        rule = await repo.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Routing rule not found")
        watch_directory_id = rule.watch_directory_id
        deleted = await repo.delete(rule_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    await _enqueue_reroute_all(watch_directory_id)


@router.post("/reroute-all/{watch_directory_id}")
async def reroute_all(watch_directory_id: int):
    """Enqueue ROUTE_FILE for all documents in a watch directory."""
    async with get_session() as session:
        wd_repo = WatchDirectoryRepository(session)
        wd = await wd_repo.get(watch_directory_id)
        if not wd:
            raise HTTPException(status_code=404, detail="Watch directory not found")

    return await _enqueue_reroute_all(watch_directory_id)
