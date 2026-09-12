"""Resume Generation API — 简历生成区（8 步向导）后端接口。

暂存退出草稿 / STAR 结构化 / 证件照 / 生成与导出（可直入简历库）。
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.api.resume_library import _serialize_document
from app.models.database import get_db
from app.models.schemas import (
    ExperienceGenerateRequest,
    ExperienceListResponse,
    ExperienceStructureRequest,
    PhotoOut,
    ResumeDraftOut,
    ResumeDraftSave,
    ResumeExportRequest,
    StarRequest,
    StarResponse,
    WizardGenerateRequest,
)
from app.services.resume_export_service import ResumeExportError, build_export
from app.services.resume_wizard_service import ResumeWizardService, WizardError

router = APIRouter()
service = ResumeWizardService()

MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5MB


def _load_llm():
    from app.llm import create_llm_provider

    try:
        return create_llm_provider()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"生成能力不可用: {e}")


# === 暂存退出 ===


@router.post("/draft", response_model=ResumeDraftOut)
async def save_draft(data: ResumeDraftSave, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """保存/覆盖生成向导草稿（暂存退出）。"""
    draft = service.save_draft(db, user["id"], data)
    return {
        "step": draft.step,
        "data": json.loads(draft.data_json) if draft.data_json else {},
        "updated_at": draft.updated_at,
    }


@router.get("/draft", response_model=ResumeDraftOut)
async def load_draft(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """读取生成向导草稿（无草稿返回 step=None）。"""
    return service.load_draft(db, user["id"])


@router.delete("/draft", status_code=204)
async def clear_draft(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """清空生成向导草稿。"""
    service.clear_draft(db, user["id"])
    return None


# === 03 经历补充：自然语言结构化 / AI 生成 ===


@router.post("/experiences/structure", response_model=ExperienceListResponse)
async def structure_experiences(
    data: ExperienceStructureRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把自然语言粗略描述结构化并润色为经历列表。"""
    llm = _load_llm()
    try:
        items = await service.structure_experiences(db, user["id"], data, llm)
    except WizardError as e:
        status = 502 if "未生成" in str(e) or "未能" in str(e) else 422
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"经历结构化失败: {e}")
    return {"items": [i.model_dump() for i in items]}


@router.post("/experiences/generate", response_model=ExperienceListResponse)
async def generate_experiences(
    data: ExperienceGenerateRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """无经历时，按画像与方向 AI 生成经历草稿。"""
    llm = _load_llm()
    try:
        items = await service.generate_experiences(db, user["id"], data, llm)
    except WizardError as e:
        status = 502 if "未生成" in str(e) else 422
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"经历生成失败: {e}")
    return {"items": [i.model_dump() for i in items]}


# === 03/04 STAR 结构化 ===


@router.post("/star", response_model=StarResponse)
async def star_structuring(
    data: StarRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把经历按 STAR 法则结构化（情境/任务/行动/成果）。"""
    llm = _load_llm()
    try:
        items = await service.star_structuring(db, user["id"], data, llm)
    except WizardError as e:
        status = 502 if "未生成" in str(e) else 422
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"STAR 结构化失败: {e}")
    return {"items": [i.model_dump() for i in items]}


# === 06 证件照 ===


@router.post("/photo", response_model=PhotoOut, status_code=201)
async def upload_photo(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """上传当前用户的简历证件照（覆盖旧照）。"""
    content = await file.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=422, detail="证件照不能超过 5MB")
    try:
        photo = service.upload_photo(db, user["id"], file.filename or "photo.jpg", content)
    except WizardError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return service.serialize_photo(photo)


@router.get("/photo", response_model=PhotoOut | None)
async def get_photo(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """读取当前用户证件照元信息。"""
    return service.serialize_photo(service.get_photo(db, user["id"]))


@router.get("/photo/file")
async def photo_file(
    id: int = Query(..., description="照片 id"),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """读取当前用户证件照文件内容。"""
    photo = service.get_photo(db, user["id"])
    if photo is None or photo.id != id:
        raise HTTPException(status_code=404, detail="证件照不存在")
    if not Path(photo.file_path).exists():
        raise HTTPException(status_code=404, detail="证件照文件不存在")
    return FileResponse(photo.file_path, media_type=f"image/{photo.mime_type}")


# === 08 生成与导出 ===


@router.post("/generate")
async def generate_resume(
    data: WizardGenerateRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """从向导数据组装简历（可选 AI 润色），可直入简历库。"""
    llm = _load_llm()
    try:
        content, doc, _version = await service.generate_resume(db, user["id"], data, llm)
    except WizardError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"简历生成失败: {e}")
    return {
        "content": content,
        "document": _serialize_document(doc, with_detail=True) if doc else None,
    }


@router.post("/export")
async def export_resume(
    data: ResumeExportRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把简历内容导出为文件（Word/HTML/Markdown/JSON）下载，可嵌证件照。"""
    photo_bytes = None
    photo_mime = None
    if data.photo_id:
        photo = service.get_photo(db, user["id"])
        if photo is not None and photo.id == data.photo_id:
            path = Path(photo.file_path)
            if path.exists():
                photo_bytes = path.read_bytes()
                photo_mime = f"image/{photo.mime_type}"
    try:
        content_bytes, media, ext = build_export(
            data.content, data.title, data.format, photo_bytes, photo_mime
        )
    except ResumeExportError as e:
        raise HTTPException(status_code=422, detail=str(e))
    safe_title = "".join(c if c.isalnum() or c in "-_. " else "_" for c in data.title).strip() or "我的简历"
    filename = f"{safe_title}.{ext}"
    return Response(
        content=content_bytes,
        media_type=media,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )
