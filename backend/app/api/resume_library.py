"""Resume Library API — 简历库资产（阶段2 指令2-1）。

文档 / 多版本 / 区域 / 回收站 / 会话导入。
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.models.database import get_db
from app.models.schemas import (
    ImportGeneratedRequest,
    ResumeDocumentCreate,
    ResumeDocumentDetailOut,
    ResumeDocumentOut,
    ResumeDocumentUpdate,
    ResumeSectionOut,
    ResumeSectionUpdate,
    ResumeVersionCreate,
    ResumeVersionOut,
    SectionAdoptRequest,
    SectionRewriteRequest,
    SessionImportRequest,
    VersionPagePreferenceRequest,
)
from app.services.resume_library_service import ResumeLibraryError, ResumeLibraryService
from app.services.section_rewrite_service import SectionRewriteError, SectionRewriteService

router = APIRouter()
service = ResumeLibraryService()
rewrite_service = SectionRewriteService()


def _safe_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _serialize_section(section) -> dict[str, Any]:
    return {
        "id": section.id,
        "resume_version_id": section.resume_version_id,
        "page_number": section.page_number,
        "section_type": section.section_type,
        "title": section.title,
        "content": section.content,
        "bounding_box": _safe_json(section.bounding_box),
        "sort_order": section.sort_order,
        "created_at": section.created_at,
        "updated_at": section.updated_at,
    }


def _serialize_version(version, current_version_id: int | None = None, with_content: bool = True) -> dict[str, Any]:
    return {
        "id": version.id,
        "document_id": version.document_id,
        "session_id": version.session_id,
        "version": version.version,
        "content": _safe_json(version.content_json) if with_content else None,
        "render_config": _safe_json(version.render_config_json),
        "sections": [_serialize_section(s) for s in version.sections],
        "is_current": version.id == current_version_id,
        "created_at": version.created_at,
    }


def _serialize_document(doc, with_detail: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": doc.id,
        "title": doc.title,
        "source": doc.source,
        "current_version_id": doc.current_version_id,
        "version_count": len(doc.versions),
        "deleted_at": doc.deleted_at,
        "notes": doc.notes,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }
    if with_detail:
        data["versions"] = [_serialize_version(v, doc.current_version_id) for v in doc.versions]
        current = next((v for v in doc.versions if v.id == doc.current_version_id), None)
        data["current_version"] = _serialize_version(current, doc.current_version_id) if current else None
    return data


@router.get("/recycle-bin", response_model=list[ResumeDocumentOut])
async def list_recycle_bin(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """回收站：已软删除的简历文档。"""
    return [_serialize_document(d) for d in service.list_deleted(db, user["id"])]


@router.get("", response_model=list[ResumeDocumentOut])
async def list_documents(
    include_deleted: bool = Query(default=False, description="是否包含回收站文档"),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return [_serialize_document(d) for d in service.list_documents(db, user["id"], include_deleted=include_deleted)]


@router.post("", response_model=ResumeDocumentOut, status_code=201)
async def create_document(data: ResumeDocumentCreate, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        doc = service.create_document(db, user["id"], data)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc)


@router.get("/{doc_id}", response_model=ResumeDocumentDetailOut)
async def get_document(doc_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        doc = service.get_document(db, user["id"], doc_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _serialize_document(doc, with_detail=True)


@router.patch("/{doc_id}", response_model=ResumeDocumentOut)
async def update_document(
    doc_id: int,
    data: ResumeDocumentUpdate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        doc = service.rename_document(db, user["id"], doc_id, data)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc)


@router.delete("/{doc_id}", status_code=200)
async def delete_document(
    doc_id: int,
    purge: bool = Query(default=False, description="true=彻底删除（不可恢复），false=移入回收站"),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        if purge:
            service.purge_document(db, user["id"], doc_id)
        else:
            service.soft_delete_document(db, user["id"], doc_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "已彻底删除" if purge else "已移入回收站"}


@router.post("/{doc_id}/restore", response_model=ResumeDocumentOut)
async def restore_document(doc_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        doc = service.restore_document(db, user["id"], doc_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _serialize_document(doc)


@router.post("/{doc_id}/versions", response_model=ResumeVersionOut, status_code=201)
async def add_version(
    doc_id: int,
    data: ResumeVersionCreate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        version = service.add_version(db, user["id"], doc_id, data)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_version(version, current_version_id=version.id)


@router.get("/{doc_id}/versions", response_model=list[ResumeVersionOut])
async def list_versions(doc_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        doc = service.get_document(db, user["id"], doc_id, include_deleted=True)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [_serialize_version(v, doc.current_version_id) for v in service.list_versions(db, user["id"], doc_id)]


@router.get("/versions/{version_id}", response_model=ResumeVersionOut)
async def get_version(version_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        version = service.get_version(db, user["id"], version_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _serialize_version(version, current_version_id=version.document.current_version_id if version.document else None)


@router.post("/versions/{version_id}/rollback", response_model=ResumeDocumentOut)
async def rollback_version(
    version_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把文档当前版本指回该历史版本（非破坏性回滚）。"""
    try:
        version = service.get_version(db, user["id"], version_id)
        doc = service.rollback_version(db, user["id"], version.document_id, version_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc)


@router.post("/versions/{version_id}/page-preference", response_model=ResumeVersionOut)
async def set_page_preference(
    version_id: int,
    data: VersionPagePreferenceRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """更新版本页数偏好（1 页 / 可接受 2 页），写入 render_config.page_preference（阶段3 3-2）。"""
    try:
        version = service.set_page_preference(db, user["id"], version_id, data.page_preference)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_version(version, current_version_id=version.document.current_version_id if version.document else None)


@router.get("/versions/{version_id}/sections", response_model=list[ResumeSectionOut])
async def list_sections(version_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        sections = service.list_sections(db, user["id"], version_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [_serialize_section(s) for s in sections]


@router.patch("/sections/{section_id}", response_model=ResumeSectionOut)
async def update_section(
    section_id: int,
    data: ResumeSectionUpdate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        section = service.update_section(db, user["id"], section_id, data)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_section(section)


@router.post("/sections/{section_id}/rewrite")
async def rewrite_section(
    section_id: int,
    data: SectionRewriteRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """区域改写：生成多条候选（不覆盖原文；引入画像外数字/经历时带核对标记）。"""
    try:
        return await rewrite_service.generate_candidates(
            db,
            user["id"],
            section_id,
            data.instruction,
            conversation_history=data.conversation_history,
            jd_analysis=data.jd_analysis,
        )
    except SectionRewriteError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        # BaseAgent 的 AGENT_TIMEOUT 到点抛 TimeoutError，映射为可读的 504
        raise HTTPException(status_code=504, detail="改写生成超时（LLM 响应过慢），请稍后重试或简化指令")
    except ValueError as e:
        # LLM provider 初始化失败（缺 key）等环境性错误
        raise HTTPException(status_code=503, detail=f"改写能力不可用: {e}")


@router.post("/versions/{version_id}/adopt-rewrite", response_model=ResumeVersionOut)
async def adopt_section_rewrite(
    version_id: int,
    data: SectionAdoptRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """采纳区域改写：生成新版本（保留旧版本可回滚），并把当前版本指针切过去。"""
    try:
        version = service.adopt_section_rewrite(db, user["id"], version_id, data.section_id, data.rewrite)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_version(version, current_version_id=version.id)


@router.post("/import-from-session", response_model=ResumeDocumentDetailOut, status_code=201)
async def import_from_session(
    data: SessionImportRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把聊天会话最新生成的简历导入简历库。"""
    try:
        service.find_session(db, user["id"], data.session_id)
        doc, _version = service.import_from_session(db, user["id"], data.session_id)
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc, with_detail=True)


@router.post("/import-generated", response_model=ResumeDocumentDetailOut, status_code=201)
async def import_generated(
    data: ImportGeneratedRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """把结构化简历内容导入简历库（生成区产物，source=generation）。"""
    try:
        doc, _version = service.import_generated(
            db, user["id"], data.title, data.content, data.page_preference
        )
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc, with_detail=True)


@router.post("/import-upload", response_model=ResumeDocumentDetailOut, status_code=201)
async def import_upload(
    title: str = Form(..., description="简历名称"),
    file: UploadFile = File(..., description="简历文件（PDF/DOCX/TXT/MD）"),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """上传 Word/PDF/TXT/MD 简历 → 解析 → 导入简历库（source=upload）。"""
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="文件不能超过 20MB")
    try:
        doc, _version = await service.import_uploaded_file(
            db,
            user["id"],
            title,
            base64.b64encode(content).decode(),
            file.filename or "resume.txt",
        )
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc, with_detail=True)
