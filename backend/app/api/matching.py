"""Job Matching API — 岗位匹配任务化（阶段2 指令2-4）。

岗位 JD 资产 + 匹配任务（分数/阶段历史/差距解释）+ 定向简历草稿导入简历库。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.models.database import get_db
from app.models.schemas import (
    JobPostingCreate,
    JobPostingOut,
    MatchRunRequest,
    MatchTaskCreate,
    MatchTaskOut,
    ResumeDocumentDetailOut,
)
from app.services.matching_service import MatchError, MatchService

router = APIRouter()
service = MatchService()


@router.get("/postings", response_model=list[JobPostingOut])
async def list_postings(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    return [service.serialize_posting(p) for p in service.list_postings(db, user["id"])]


@router.post("/postings", response_model=JobPostingOut, status_code=201)
async def create_posting(data: JobPostingCreate, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    posting = service.create_posting(db, user["id"], data)
    return service.serialize_posting(posting)


@router.delete("/postings/{posting_id}", status_code=204)
async def delete_posting(posting_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        service.delete_posting(db, user["id"], posting_id)
    except MatchError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None


@router.get("/tasks", response_model=list[MatchTaskOut])
async def list_tasks(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    return [service.serialize_task(t) for t in service.list_tasks(db, user["id"])]


@router.post("/tasks", response_model=MatchTaskOut, status_code=201)
async def create_task(data: MatchTaskCreate, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        task = service.create_task(db, user["id"], data)
    except MatchError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return service.serialize_task(task)


@router.get("/tasks/{task_id}", response_model=MatchTaskOut)
async def get_task(task_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        task = service.get_task(db, user["id"], task_id)
    except MatchError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return service.serialize_task(task)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        service.delete_task(db, user["id"], task_id)
    except MatchError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None


@router.post("/tasks/{task_id}/run", response_model=MatchTaskOut)
async def run_matching(
    task_id: int,
    data: MatchRunRequest,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """执行匹配分析（JD 分析 → 差距定位 → 定向草稿）。"""
    try:
        from app.llm import create_llm_provider

        llm = create_llm_provider()
        agents = service.build_match_agents(llm)
        task = await service.run_matching(db, user["id"], task_id, agents, with_draft=data.with_draft)
    except MatchError as e:
        # 任务失败时 stage=failed 已落库，前端可看到现场；HTTP 仍返回可读错误
        status = 422 if "暂无已确认画像" in str(e) or "缺少岗位" in str(e) else 502
        raise HTTPException(status_code=status, detail=str(e))
    except ValueError as e:
        # LLM provider 初始化失败（缺 key）等环境性错误
        raise HTTPException(status_code=503, detail=f"匹配能力不可用: {e}")
    return service.serialize_task(task)


@router.post("/tasks/{task_id}/export-draft", response_model=ResumeDocumentDetailOut, status_code=201)
async def export_draft(task_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """把定向简历草稿导入简历库（生成新文档）。"""
    from app.api.resume_library import _serialize_document
    from app.services.resume_library_service import ResumeLibraryError

    try:
        doc, _version = service.export_draft_to_library(db, user["id"], task_id)
    except MatchError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ResumeLibraryError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize_document(doc, with_detail=True)
