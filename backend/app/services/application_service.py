"""ApplicationService — 投递记录（阶段3 指令3-3）。

手动新增/管理投递记录，支持按公司/岗位模糊搜索、按状态筛选、状态汇总（进行中/通过/未通过）。
status 复用 job_applications.status 字符串列（无 schema 变更）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import JobApplication
from app.models.schemas import JobApplicationCreate, JobApplicationUpdate

# 状态（阶段）：参考图 投递记录册 的「状态」维度
ALLOWED_STATUS = {"applied", "written_test", "interview", "offer", "rejected"}
STATUS_LABEL = {
    "applied": "已投递",
    "written_test": "笔试中",
    "interview": "面试中",
    "offer": "offer",
    "rejected": "未通过",
}
# 结果（outcome）推导：进行中 / 通过 / 未通过
RESULT_BY_STATUS = {
    "applied": "ongoing",
    "written_test": "ongoing",
    "interview": "ongoing",
    "offer": "passed",
    "rejected": "failed",
}


class ApplicationError(ValueError):
    """投递记录业务错误。"""


class ApplicationService:
    """投递记录 CRUD + 搜索/筛选/汇总。"""

    def create(self, db: DBSession, user_id: int, data: JobApplicationCreate) -> JobApplication:
        self._ensure_status(data.status)
        app = JobApplication(
            user_id=user_id,
            company=data.company,
            job_title=data.job_title,
            status=data.status,
            notes=data.notes,
            applied_at=data.applied_at,
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    def list(
        self,
        db: DBSession,
        user_id: int,
        q: str | None = None,
        status: str | None = None,
        result: str | None = None,
    ) -> list[JobApplication]:
        query = db.query(JobApplication).filter(JobApplication.user_id == user_id)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (JobApplication.company.like(like)) | (JobApplication.job_title.like(like))
            )
        if status:
            self._ensure_status(status)
            query = query.filter(JobApplication.status == status)
        if result:
            statuses = [s for s, r in RESULT_BY_STATUS.items() if r == result]
            if not statuses:
                raise ApplicationError(f"result 非法: {result!r}（允许 ongoing | passed | failed）")
            query = query.filter(JobApplication.status.in_(statuses))
        return query.order_by(JobApplication.applied_at.desc(), JobApplication.id.desc()).all()

    def get(self, db: DBSession, user_id: int, app_id: int) -> JobApplication:
        app = (
            db.query(JobApplication)
            .filter(JobApplication.id == app_id, JobApplication.user_id == user_id)
            .first()
        )
        if app is None:
            raise ApplicationError("投递记录不存在")
        return app

    def update(self, db: DBSession, user_id: int, app_id: int, data: JobApplicationUpdate) -> JobApplication:
        app = self.get(db, user_id, app_id)
        updates = data.model_dump(exclude_unset=True, exclude_none=True)
        if "status" in updates:
            self._ensure_status(updates["status"])
        for field, value in updates.items():
            setattr(app, field, value)
        db.commit()
        db.refresh(app)
        return app

    def delete(self, db: DBSession, user_id: int, app_id: int) -> None:
        app = self.get(db, user_id, app_id)
        db.delete(app)
        db.commit()

    def summary(self, db: DBSession, user_id: int) -> dict[str, Any]:
        """状态汇总：总条数 + 各状态 + 结果（进行中/通过/未通过）。"""
        apps = (
            db.query(JobApplication)
            .filter(JobApplication.user_id == user_id)
            .all()
        )
        by_status = {s: 0 for s in ALLOWED_STATUS}
        by_result = {"ongoing": 0, "passed": 0, "failed": 0}
        for app in apps:
            by_status[app.status] = by_status.get(app.status, 0) + 1
            by_result[RESULT_BY_STATUS.get(app.status, "ongoing")] += 1
        return {
            "total": len(apps),
            "by_status": by_status,
            "by_result": by_result,
        }

    @staticmethod
    def serialize(app: JobApplication) -> dict[str, Any]:
        return {
            "id": app.id,
            "company": app.company,
            "job_title": app.job_title,
            "status": app.status,
            "result": RESULT_BY_STATUS.get(app.status, "ongoing"),
            "notes": app.notes,
            "applied_at": app.applied_at,
            "created_at": app.created_at,
        }

    @staticmethod
    def _ensure_status(status: str) -> None:
        if status not in ALLOWED_STATUS:
            raise ApplicationError(f"status 非法: {status!r}，允许 {sorted(ALLOWED_STATUS)}")
