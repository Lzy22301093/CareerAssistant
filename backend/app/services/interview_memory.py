"""Interview Memory Service（v3 M3 长久陪伴）— 面试记录 + 教训提炼 + 复习计划。

- parse_interview_reply：从对话中提取面试信息（LLM + schema 校验）
- record_interview：结构化入库，失败教训更新 career_profile gaps
- build_review_plan：基于历史教训 + 当前 JD 生成针对性复习清单
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.database import SessionLocal
from app.models.orm import InterviewLog
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

# 面试信息收集顺序（clarifier 多轮追问用）
DRAFT_FIELDS = ("company", "job_title", "result", "questions", "weak_points")

# 各字段的追问问题
FIELD_QUESTIONS: dict[str, str] = {
    "company": "面试的是哪家公司？岗位是什么？（例如：腾讯，后端工程师）",
    "result": "面试结果怎么样？（通过 / 未通过 / 等通知）",
    "questions": "面试官问了哪些问题？（可列出几道印象深的）",
    "weak_points": "哪几道题或哪些方面你感觉最没把握？",
}


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


class InterviewMemoryService:
    """面试记忆：记录 / 提炼 / 复习计划。"""

    def __init__(self, db_factory=None) -> None:
        self._db_factory = db_factory or SessionLocal
        self._memory = MemoryService(db_factory=db_factory)

    def _get_db(self) -> DBSession:
        return self._db_factory()

    # === 多轮追问 ===

    def missing_fields(self, draft: dict[str, Any]) -> list[str]:
        """返回 draft 中仍缺失的字段（按收集顺序）。"""
        missing = []
        for field in DRAFT_FIELDS:
            if not _has_value(draft.get(field)):
                missing.append(field)
        # questions/weak_points 可以留空：只要求前三个必填，其余可选但会问
        return missing

    def is_complete(self, draft: dict[str, Any]) -> bool:
        """核心字段齐全即视为完成（questions/weak_points 可选）。"""
        return _has_value(draft.get("company")) and _has_value(draft.get("job_title")) and _has_value(draft.get("result"))

    def next_question(self, draft: dict[str, Any]) -> str | None:
        """返回下一个追问；已完成返回 None。"""
        if not _has_value(draft.get("company")):
            return FIELD_QUESTIONS["company"]
        if not _has_value(draft.get("job_title")):
            return "具体是什么岗位？"
        if not _has_value(draft.get("result")):
            return FIELD_QUESTIONS["result"]
        if not draft.get("questions"):
            return FIELD_QUESTIONS["questions"]
        if not draft.get("weak_points"):
            return FIELD_QUESTIONS["weak_points"]
        return None

    async def parse_interview_reply(self, llm, user_message: str, draft: dict[str, Any]) -> dict[str, Any]:
        """从用户回复提取面试信息，合并进 draft。

        Args:
            llm: LLMProvider 实例。
            user_message: 用户本轮回复。
            draft: 当前已收集的面试信息。

        Returns:
            合并后的 draft。LLM 提取失败时保留原 draft（不中断追问）。
        """
        from app.llm.structured import ainvoke_json_with_schema
        from app.prompts.interview_record import INTERVIEW_PARSE_PROMPT
        from app.services.interview_schema import InterviewParseOutput

        user_content = (
            f"用户消息：\n{user_message[:1000]}\n\n"
            f"当前已收集：\n{json.dumps(draft, ensure_ascii=False)[:1000]}"
        )
        try:
            parsed = await ainvoke_json_with_schema(
                llm, INTERVIEW_PARSE_PROMPT, user_content, InterviewParseOutput,
                temperature=0.2, max_tokens=1024,
            )
        except ValueError as e:
            logger.warning(f"面试信息解析失败: {e}")
            return dict(draft)

        updated = dict(draft)
        if parsed.company and not _has_value(updated.get("company")):
            updated["company"] = parsed.company
        if parsed.job_title and not _has_value(updated.get("job_title")):
            updated["job_title"] = parsed.job_title
        if parsed.result:
            updated["result"] = parsed.result
        if parsed.questions:
            # 合并去重
            existing = list(updated.get("questions") or [])
            seen = {str(q).strip().lower() for q in existing}
            for q in parsed.questions:
                key = str(q).strip().lower()
                if key and key not in seen:
                    existing.append(q)
                    seen.add(key)
            updated["questions"] = existing
        if parsed.weak_points:
            existing = list(updated.get("weak_points") or [])
            seen = {str(w).strip().lower() for w in existing}
            for w in parsed.weak_points:
                key = str(w).strip().lower()
                if key and key not in seen:
                    existing.append(w)
                    seen.add(key)
            updated["weak_points"] = existing
        if parsed.feedback:
            updated["feedback"] = parsed.feedback
        return updated

    # === 记录入库 ===

    def record_interview(self, user_id: int, draft: dict[str, Any], source: str = "real") -> InterviewLog | None:
        """把面试记录入库；失败教训同步更新 career_profile gaps。"""
        if not self.is_complete(draft):
            logger.warning(f"面试记录不完整 user={user_id}")
            return None

        db = self._get_db()
        try:
            log = InterviewLog(
                user_id=user_id,
                company=(draft.get("company") or "")[:100],
                job_title=(draft.get("job_title") or "")[:100],
                result=draft.get("result", "pending"),
                questions_json=json.dumps(draft.get("questions") or [], ensure_ascii=False),
                weak_points_json=json.dumps(draft.get("weak_points") or [], ensure_ascii=False),
                feedback=draft.get("feedback"),
                source=source,
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            logger.info(f"面试记录入库 user={user_id}, company={log.company}, result={log.result}")
        except Exception as e:
            db.rollback()
            logger.error(f"面试记录入库失败 user={user_id}: {e}")
            return None
        finally:
            db.close()

        # 失败教训 → 更新 career_profile gaps（规则合并）
        weak_points = draft.get("weak_points") or []
        if draft.get("result") == "failed" or weak_points:
            profile = self._memory.get_profile(user_id) or {}
            gaps = list(profile.get("gaps") or [])
            existing = {str(g).strip().lower() for g in gaps}
            for wp in weak_points:
                key = str(wp).strip().lower()
                if key and key not in existing:
                    gaps.append(wp)
                    existing.add(key)
            if gaps:
                self._memory.upsert_profile(
                    user_id, {"gaps": gaps}, source="interview_lessons"
                )
        return log

    # === 复习计划 ===

    def recent_lessons(self, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
        """取最近的面试教训（weak_points 非空的记录）。"""
        db = self._get_db()
        try:
            rows = (
                db.query(InterviewLog)
                .filter(InterviewLog.user_id == user_id)
                .order_by(InterviewLog.created_at.desc())
                .limit(limit)
                .all()
            )
            lessons = []
            for row in rows:
                weak = json.loads(row.weak_points_json) if row.weak_points_json else []
                questions = json.loads(row.questions_json) if row.questions_json else []
                if weak or row.result == "failed":
                    lessons.append({
                        "company": row.company,
                        "job_title": row.job_title,
                        "result": row.result,
                        "questions": questions,
                        "weak_points": weak,
                    })
            return lessons
        except Exception as e:
            logger.error(f"读取面试教训失败 user={user_id}: {e}")
            return []
        finally:
            db.close()

    async def build_review_plan(
        self,
        llm,
        user_id: int,
        jd_analysis: dict[str, Any],
        gap_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """基于历史教训 + 当前 JD 生成针对性复习清单。

        无教训或生成失败时返回 {"items": [], "has_lessons": False}。
        """
        lessons = self.recent_lessons(user_id)
        if not lessons:
            return {"items": [], "has_lessons": False}

        from app.llm.structured import ainvoke_json_with_schema
        from app.prompts.interview_record import REVIEW_PLAN_PROMPT
        from app.services.interview_schema import ReviewPlanOutput

        user_content = (
            f"历史面试教训：\n{json.dumps(lessons, ensure_ascii=False)[:3000]}\n\n"
            f"当前 JD 要求：\n{json.dumps(jd_analysis, ensure_ascii=False)[:2000]}"
        )
        if gap_analysis:
            user_content += f"\n\n当前差距分析：\n{json.dumps(gap_analysis, ensure_ascii=False)[:2000]}"

        try:
            output = await ainvoke_json_with_schema(
                llm, REVIEW_PLAN_PROMPT, user_content, ReviewPlanOutput,
                temperature=0.3, max_tokens=1536,
            )
        except ValueError as e:
            logger.warning(f"复习计划生成失败: {e}")
            return {"items": [], "has_lessons": True}

        items = [item.model_dump() for item in output.items]
        return {"items": items, "has_lessons": True, "lessons_count": len(lessons)}
