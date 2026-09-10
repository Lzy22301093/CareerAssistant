"""Applications API — 投递记录（阶段3 指令3-3）。

手动新增/管理投递记录，支持模糊搜索、状态/结果筛选、状态汇总与提醒。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.models.database import get_db
from app.models.schemas import (
    JobApplicationCreate,
    JobApplicationOut,
    JobApplicationUpdate,
)
from app.services.application_service import ApplicationError, ApplicationService

router = APIRouter()
service = ApplicationService()


@router.get("", response_model=list[JobApplicationOut])
async def list_applications(
    q: str | None = Query(default=None, description="按公司或岗位模糊搜索"),
    status: str | None = Query(default=None, description="applied|written_test|interview|offer|rejected"),
    result: str | None = Query(default=None, description="ongoing|passed|failed"),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        apps = service.list(db, user["id"], q=q, status=status, result=result)
    except ApplicationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [service.serialize(a) for a in apps]


@router.get("/summary")
async def application_summary(user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    """状态汇总（总条数 + 各状态 + 进行中/通过/未通过）。"""
    return service.summary(db, user["id"])


@router.post("", response_model=JobApplicationOut, status_code=201)
async def create_application(
    data: JobApplicationCreate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        app = service.create(db, user["id"], data)
    except ApplicationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return service.serialize(app)


@router.get("/{app_id}", response_model=JobApplicationOut)
async def get_application(app_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        app = service.get(db, user["id"], app_id)
    except ApplicationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return service.serialize(app)


@router.patch("/{app_id}", response_model=JobApplicationOut)
async def update_application(
    app_id: int,
    data: JobApplicationUpdate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        app = service.update(db, user["id"], app_id, data)
    except ApplicationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return service.serialize(app)


@router.delete("/{app_id}", status_code=204)
async def delete_application(app_id: int, user: dict = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        service.delete(db, user["id"], app_id)
    except ApplicationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None
