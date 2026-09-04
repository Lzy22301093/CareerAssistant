"""Profile API — 个人画像 / 知识库（阶段0 指令0-3）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.models.database import get_db
from app.models.schemas import (
    EvidenceCreate,
    ProfileEvidenceOut,
    ProfileItemCreate,
    ProfileItemOut,
    ProfileItemUpdate,
    StatusChange,
)
from app.services.profile_service import ProfileService, ProfileServiceError

router = APIRouter()
service = ProfileService()


def _serialize_item(item) -> dict:
    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "content": item.content,
        "item_type": item.item_type,
        "confidence": item.confidence,
        "visibility": item.visibility,
        "status": item.status,
        "sort_order": item.sort_order,
        "evidences": [
            {
                "id": e.id,
                "source_type": e.source_type,
                "source_id": e.source_id,
                "quote": e.quote,
                "verified_by_user": e.verified_by_user,
                "created_at": e.created_at,
            }
            for e in item.evidences
        ],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/categories")
async def get_categories(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """按分类聚合条目数量（节点星座图/导航）。"""
    return service.category_summary(db, user["id"])


@router.get("/items", response_model=list[ProfileItemOut])
async def list_items(
    category: str | None = None,
    status: str | None = None,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    items = service.list_items(db, user["id"], category=category, status=status)
    return [_serialize_item(i) for i in items]


@router.get("/items/{item_id}", response_model=ProfileItemOut)
async def get_item(item_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        item = service.get_item(db, user["id"], item_id)
    except ProfileServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _serialize_item(item)


@router.post("/items", response_model=ProfileItemOut, status_code=201)
async def create_item(data: ProfileItemCreate, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        item = service.create_item(db, user["id"], data)
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_item(item)


@router.patch("/items/{item_id}", response_model=ProfileItemOut)
async def update_item(
    item_id: int,
    data: ProfileItemUpdate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        item = service.update_item(db, user["id"], item_id, data)
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_item(item)


@router.post("/items/{item_id}/status", response_model=ProfileItemOut)
async def change_status(
    item_id: int,
    data: StatusChange,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        item = service.change_status(db, user["id"], item_id, data.status)
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_item(item)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        service.delete_item(db, user["id"], item_id)
    except ProfileServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None


@router.post("/items/{item_id}/evidences", response_model=ProfileEvidenceOut, status_code=201)
async def add_evidence(
    item_id: int,
    data: EvidenceCreate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        ev = service.add_evidence(db, user["id"], item_id, data)
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "id": ev.id,
        "source_type": ev.source_type,
        "source_id": ev.source_id,
        "quote": ev.quote,
        "verified_by_user": ev.verified_by_user,
        "created_at": ev.created_at,
    }
