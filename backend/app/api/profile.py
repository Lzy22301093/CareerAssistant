"""Profile API — 个人画像 / 知识库（阶段0 指令0-3）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.models.database import get_db
from app.models.schemas import (
    DirectionConfirmRequest,
    EvidenceCreate,
    ProfileEvidenceOut,
    ProfileFormOut,
    ProfileFormSave,
    ProfileItemCreate,
    ProfileItemOut,
    ProfileItemUpdate,
    SoftInfoSaveRequest,
    SoftInfoSuggestion,
    StatusChange,
)
from app.services.direction_service import DirectionError, DirectionService
from app.services.profile_form_service import ProfileFormService
from app.services.profile_service import ProfileService, ProfileServiceError
from app.services.soft_info_service import SoftInfoError, SoftInfoService

router = APIRouter()
service = ProfileService()
direction_service = DirectionService()
soft_info_service = SoftInfoService()
form_service = ProfileFormService()


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


# === 画像方向推荐（阶段3 指令3-1） ===


@router.post("/directions/recommend")
async def recommend_directions(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """基于已确认画像生成岗位方向候选（3~8 条，供用户选 1~3）。"""
    from app.llm import create_llm_provider

    try:
        llm = create_llm_provider()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"方向推荐能力不可用: {e}")

    try:
        candidates = await direction_service.recommend_directions(db, user["id"], llm)
    except DirectionError as e:
        # 无画像 → 422；LLM 未生成有效候选 → 502
        status = 422 if "暂无已确认画像" in str(e) else 502
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"画像方向推荐失败: {e}")
    return candidates


@router.post("/directions/confirm", status_code=201)
async def confirm_directions(
    data: DirectionConfirmRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把用户选中的方向（1~3 个）写入为 target 分类的 confirmed 画像条目。"""
    try:
        items = direction_service.confirm_directions(db, user["id"], data.selected)
    except DirectionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [_serialize_item(i) for i in items]


# === 软性信息（阶段3 指令3-2） ===


@router.post("/soft-info/generate", response_model=SoftInfoSuggestion)
async def generate_soft_info(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """基于已确认画像生成软性信息建议（自我评价可 AI 生成）。"""
    from app.llm import create_llm_provider

    try:
        llm = create_llm_provider()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"软性信息能力不可用: {e}")

    try:
        return await soft_info_service.generate_soft_info(db, user["id"], llm)
    except SoftInfoError as e:
        status = 422 if "暂无已确认画像" in str(e) else 502
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"软性信息生成失败: {e}")


@router.post("/soft-info/save", status_code=201)
async def save_soft_info(
    data: SoftInfoSaveRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把软性信息字段写入为 category=soft 的 confirmed 画像条目。"""
    try:
        items = soft_info_service.save_soft_info(db, user["id"], data)
    except SoftInfoError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [_serialize_item(i) for i in items]


# === 结构化画像表单（知识库 分阶段向导，阶段3） ===


@router.get("/form", response_model=ProfileFormOut)
async def get_profile_form(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """读取知识库分阶段向导已保存的数据（基本信息/教育/奖项/社交/其他）。"""
    return form_service.load(db, user["id"])


@router.post("/form", response_model=ProfileFormOut)
async def save_profile_form(
    data: ProfileFormSave,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """保存知识库分阶段向导（upsert，幂等），返回保存后的数据。"""
    try:
        return form_service.save(db, user["id"], data)
    except ProfileServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
