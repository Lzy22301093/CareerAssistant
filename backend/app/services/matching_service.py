"""MatchService — 岗位匹配任务化（阶段2 指令2-4）。

JobPosting（JD 资产）+ MatchTask（JD × 简历版本 × 页数偏好 × 分数 × 阶段历史）。
匹配复用现有 gap 引擎（jd_analyzer → gap_analyzer），定向草稿复用 content_generator；
分数解释 = gap 结果（优势/缺口/建议，缺口按类别即维度）。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import JobPosting, MatchTask, ResumeVersion
from app.models.schemas import JobPostingCreate, MatchTaskCreate
from app.services.profile_service import build_profile_context
from app.services.resume_library_service import parse_json_object

ALLOWED_PAGE_PREF = {"one_page", "two_pages"}
STAGES = ("created", "analyzing", "done", "failed")

# 参考图 03 的阶段口径（前端进度条文案与后端 stage_history 对齐）
RUN_STEPS = ["分析需求", "匹配定位", "重写内容", "校验格式"]


class MatchError(ValueError):
    """匹配业务错误。"""


def build_match_agents(llm: Any) -> dict[str, Any]:
    """匹配链路 agent：沿用 create_agents 的模型分层（jd/gap=FAST_MODEL，content=主模型）。

    必须经工厂创建而非直接实例化，否则 jd/gap 会回落到昂贵的主模型（延迟与成本劣化）。
    """
    from app.agents import create_agents

    all_agents = create_agents(llm)
    return {
        "jd_analyzer": all_agents["jd_analyzer"],
        "gap_analyzer": all_agents["gap_analyzer"],
        "content_generator": all_agents["content_generator"],
    }


class MatchService:
    """岗位资产 + 匹配任务。"""

    # ---- 岗位资产 ----

    def create_posting(self, db: DBSession, user_id: int, data: JobPostingCreate) -> JobPosting:
        posting = JobPosting(
            user_id=user_id,
            company=data.company,
            title=data.title,
            jd_text=data.jd_text,
            jd_image=data.jd_image,
            source=data.source,
        )
        db.add(posting)
        db.commit()
        db.refresh(posting)
        return posting

    def list_postings(self, db: DBSession, user_id: int) -> list[JobPosting]:
        return (
            db.query(JobPosting)
            .filter(JobPosting.user_id == user_id)
            .order_by(JobPosting.updated_at.desc(), JobPosting.id.desc())
            .all()
        )

    def get_posting(self, db: DBSession, user_id: int, posting_id: int) -> JobPosting:
        posting = (
            db.query(JobPosting).filter(JobPosting.id == posting_id, JobPosting.user_id == user_id).first()
        )
        if posting is None:
            raise MatchError("岗位不存在")
        return posting

    def delete_posting(self, db: DBSession, user_id: int, posting_id: int) -> None:
        posting = self.get_posting(db, user_id, posting_id)
        db.delete(posting)
        db.commit()

    # ---- 匹配任务 ----

    def create_task(self, db: DBSession, user_id: int, data: MatchTaskCreate) -> MatchTask:
        if data.page_preference not in ALLOWED_PAGE_PREF:
            raise MatchError(f"page_preference 非法: {data.page_preference!r}")
        self.get_posting(db, user_id, data.job_posting_id)
        if data.resume_version_id is not None:
            version = db.query(ResumeVersion).filter(ResumeVersion.id == data.resume_version_id).first()
            if version is None:
                raise MatchError("简历版本不存在")
        task = MatchTask(
            user_id=user_id,
            job_posting_id=data.job_posting_id,
            resume_version_id=data.resume_version_id,
            page_preference=data.page_preference,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def get_task(self, db: DBSession, user_id: int, task_id: int) -> MatchTask:
        task = db.query(MatchTask).filter(MatchTask.id == task_id, MatchTask.user_id == user_id).first()
        if task is None:
            raise MatchError("匹配任务不存在")
        return task

    def list_tasks(self, db: DBSession, user_id: int) -> list[MatchTask]:
        return (
            db.query(MatchTask)
            .filter(MatchTask.user_id == user_id)
            .order_by(MatchTask.updated_at.desc(), MatchTask.id.desc())
            .all()
        )

    def delete_task(self, db: DBSession, user_id: int, task_id: int) -> None:
        task = self.get_task(db, user_id, task_id)
        db.delete(task)
        db.commit()

    # ---- 匹配分析（复用 gap 引擎 + 定向草稿） ----

    async def run_matching(
        self,
        db: DBSession,
        user_id: int,
        task_id: int,
        agents: dict[str, Any],
        with_draft: bool = True,
    ) -> MatchTask:
        """执行匹配：JD 分析 → 差距定位（分数+可解释维度）→ 定向简历草稿。

        agents: {"jd_analyzer", "gap_analyzer", "content_generator"}（duck-typed，测试可注入 Fake）。
        阶段历史写入 summary_json.stage_history；失败置 stage=failed 并保留现场，不丢任务。
        """
        task = self.get_task(db, user_id, task_id)
        posting = task.job_posting
        if posting is None or not (posting.jd_text or "").strip():
            raise MatchError("任务缺少岗位 JD 内容")

        history: list[dict[str, Any]] = self._history(task)
        history.append({"step": "分析需求", "status": "running", "at": datetime.now().isoformat(timespec="seconds")})
        task.stage = "analyzing"
        task.summary_json = json.dumps({"stage_history": history}, ensure_ascii=False)
        db.commit()

        try:
            profile_ctx = build_profile_context(db, user_id)
            if not profile_ctx:
                raise MatchError("暂无已确认画像，请先到个人知识库完善并确认画像条目")
            resume_content: dict[str, Any] | None = None
            if task.resume_version_id:
                version = db.query(ResumeVersion).filter(ResumeVersion.id == task.resume_version_id).first()
                resume_content = parse_json_object(version.content_json) if version else None

            jd_analysis = await agents["jd_analyzer"].run(jd_text=posting.jd_text)
            history[-1]["status"] = "done"
            history.append({"step": "匹配定位", "status": "running", "at": datetime.now().isoformat(timespec="seconds")})

            gap = await agents["gap_analyzer"].run(jd_analysis=jd_analysis, profile=profile_ctx)
            score = max(0, min(100, int(gap.get("overall_score") or 0)))
            history[-1]["status"] = "done"
            if with_draft:
                history.append({"step": "重写内容", "status": "running", "at": datetime.now().isoformat(timespec="seconds")})
                page_hint = "两页，可保留完整内容" if task.page_preference == "two_pages" else "一页，内容精简"
                draft = await agents["content_generator"].run(
                    profile=profile_ctx,
                    jd_analysis=jd_analysis,
                    gap_analysis=gap,
                    user_instructions=(
                        f"针对该岗位生成定向简历草稿（页数偏好：{page_hint}）。"
                        "优先在事实层面强化差距分析中可补强的点，不得捏造经历或数字。"
                    ),
                )
                history[-1]["status"] = "done"
            else:
                draft = None
            history.append({"step": "校验格式", "status": "done", "at": datetime.now().isoformat(timespec="seconds")})
        except MatchError:
            task.stage = "failed"
            history[-1]["status"] = "failed"
            task.summary_json = json.dumps({"stage_history": history}, ensure_ascii=False)
            db.commit()
            raise
        except Exception as e:  # LLM/网络等运行时错误 → 任务标记失败但保留现场
            task.stage = "failed"
            history[-1]["status"] = "failed"
            task.summary_json = json.dumps(
                {"stage_history": history, "error": str(e)[:500]}, ensure_ascii=False
            )
            db.commit()
            raise MatchError(f"匹配分析失败: {e}") from e

        task.score = score
        task.stage = "done"
        task.summary_json = json.dumps(
            {
                "company": posting.company,
                "posting_title": posting.title,
                "score": score,
                "overall": gap.get("overall_score"),
                "strengths": gap.get("strengths") or [],
                "gaps": gap.get("gaps") or [],
                "recommendations": gap.get("recommendations") or [],
                "jd_analysis": jd_analysis,
                "draft": draft,
                "stage_history": history,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
        )
        db.commit()
        db.refresh(task)
        return task

    def export_draft_to_library(self, db: DBSession, user_id: int, task_id: int) -> tuple[Any, Any]:
        """把匹配结果的定向简历草稿导入简历库（生成新文档 + v1）。"""
        from app.models.schemas import ResumeDocumentCreate, ResumeVersionCreate
        from app.services.resume_library_service import ResumeLibraryService

        task = self.get_task(db, user_id, task_id)
        summary = parse_json_object(task.summary_json) or {}
        draft = summary.get("draft")
        if not draft:
            raise MatchError("该任务还没有定向简历草稿")
        company = summary.get("company") or "岗位"
        title = summary.get("posting_title") or ""
        lib = ResumeLibraryService()
        doc = lib.create_document(
            db, user_id, ResumeDocumentCreate(title=f"{company}·{title} 定向简历".strip("·"), source="manual")
        )
        version = lib.add_version(db, user_id, doc.id, ResumeVersionCreate(content=draft))
        return doc, version

    # ---- 序列化 ----

    @staticmethod
    def serialize_posting(posting: JobPosting) -> dict[str, Any]:
        return {
            "id": posting.id,
            "company": posting.company,
            "title": posting.title,
            "jd_text": posting.jd_text,
            "source": posting.source,
            "task_count": len(posting.match_tasks),
            "created_at": posting.created_at,
            "updated_at": posting.updated_at,
        }

    @staticmethod
    def serialize_task(task: MatchTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "job_posting_id": task.job_posting_id,
            "company": task.job_posting.company if task.job_posting else None,
            "posting_title": task.job_posting.title if task.job_posting else None,
            "resume_version_id": task.resume_version_id,
            "page_preference": task.page_preference,
            "score": task.score,
            "stage": task.stage,
            "summary": parse_json_object(task.summary_json),
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    @staticmethod
    def _history(task: MatchTask) -> list[dict[str, Any]]:
        summary = parse_json_object(task.summary_json) or {}
        history = summary.get("stage_history")
        return history if isinstance(history, list) else []
