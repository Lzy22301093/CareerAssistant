"""ResumeWizardService — 简历生成区（8 步向导）后端。

能力：
- 暂存退出：resume_drafts（每用户一份草稿：当前步骤 + 数据快照）
- STAR 结构化：经历 → 情境/任务/行动/成果（ainvoke_json_with_schema，schema 校验）
- 生成与导出：向导数据 → ResumeContent（可选 AI 润色）→ 导入简历库（source=generation）
- 证件照：resume_photos（每用户一张，重传覆盖）
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.models.orm import ResumeDraft, ResumePhoto
from app.models.schemas import (
    ResumeContent,
    ResumeDraftSave,
    StarBatch,
    StarRequest,
    StarResultItem,
    WizardGenerateRequest,
)
from app.services.resume_library_service import parse_json_object

logger = logging.getLogger(__name__)

# 默认模块顺序（与参考图「预览与微调」的模块集对齐）
DEFAULT_MODULE_ORDER = [
    "基本信息",
    "求职意向",
    "教育背景",
    "实习/工作经历",
    "项目经历",
    "技能",
    "自我评价",
    "证书/荣誉",
]

ALLOWED_PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

STAR_SYSTEM_PROMPT = (
    "你是简历经历结构化专家。请把每条经历按 STAR 法则改写为四个字段："
    "situation（情境）、task（任务）、action（行动）、result（结果）。\n"
    "要求：基于用户提供的事实，不捏造；action 具体到方法/技术，result 尽量量化或写实；"
    "保留原经历的 exp_type/company/title。\n"
    "只输出 JSON：{\"items\":[{\"exp_type\":\"...\",\"company\":\"...\",\"title\":\"...\","
    "\"situation\":\"...\",\"task\":\"...\",\"action\":\"...\",\"result\":\"...\"}]}"
)

POLISH_SYSTEM_PROMPT = (
    "你是专业中文简历润色助手。请润色以下简历内容：统一语感、使表达更专业有力、"
    "在不改变事实的前提下改善措辞与量化表达。\n"
    "保持 sections 结构与标题不变，输出 JSON："
    '{"sections":[{"title":"...","content":"..."}],"raw_text":"完整纯文本"}'
)


class WizardError(ValueError):
    """生成区业务错误。"""


class ResumeWizardService:
    """8 步向导后端能力。"""

    # ---- 暂存退出（01-08 草稿） ----

    def save_draft(self, db: DBSession, user_id: int, data: ResumeDraftSave) -> ResumeDraft:
        draft = (
            db.query(ResumeDraft).filter(ResumeDraft.user_id == user_id).first()
        )
        if draft is None:
            draft = ResumeDraft(user_id=user_id, step=data.step, data_json=json.dumps(data.data, ensure_ascii=False))
            db.add(draft)
        else:
            draft.step = data.step
            draft.data_json = json.dumps(data.data, ensure_ascii=False)
        db.commit()
        db.refresh(draft)
        return draft

    def load_draft(self, db: DBSession, user_id: int) -> dict[str, Any]:
        draft = (
            db.query(ResumeDraft).filter(ResumeDraft.user_id == user_id).first()
        )
        if draft is None:
            return {"step": None, "data": {}, "updated_at": None}
        return {
            "step": draft.step,
            "data": parse_json_object(draft.data_json) or {},
            "updated_at": draft.updated_at,
        }

    def clear_draft(self, db: DBSession, user_id: int) -> None:
        draft = (
            db.query(ResumeDraft).filter(ResumeDraft.user_id == user_id).first()
        )
        if draft is not None:
            db.delete(draft)
            db.commit()

    # ---- 03/04 STAR 结构化 ----

    async def star_structuring(
        self,
        db: DBSession,
        user_id: int,
        req: StarRequest,
        llm: Any,
    ) -> list[StarResultItem]:
        experiences = req.experiences or []
        if not experiences:
            return []

        from app.llm.structured import ainvoke_json_with_schema

        user_content = (
            "请把以下每条经历按 STAR 法则结构化输出：\n"
            + json.dumps(
                [e.model_dump() for e in experiences],
                ensure_ascii=False,
                indent=2,
            )
        )
        result = await ainvoke_json_with_schema(
            llm,
            system_prompt=STAR_SYSTEM_PROMPT,
            user_content=user_content,
            schema=StarBatch,
            max_attempts=2,
            temperature=0.4,
            max_tokens=2048,
        )
        # 兜底：LLM 缺失字段时用原始经历文本回填
        by_key = {(e.exp_type or "", e.company or "", e.title or ""): e for e in experiences}
        items: list[StarResultItem] = []
        for item in result.items:
            star = StarResultItem(
                exp_type=item.exp_type or "项目",
                company=item.company,
                title=item.title,
                situation=(item.situation or "").strip(),
                task=(item.task or "").strip(),
                action=(item.action or "").strip(),
                result=(item.result or "").strip(),
            )
            if not any([star.situation, star.task, star.action, star.result]):
                original = by_key.get((star.exp_type, star.company, star.title))
                if original:
                    star.action = original.duty or ""
                    star.result = original.achievement or ""
            items.append(star)
        if not items:
            raise WizardError("经历未生成有效的 STAR 结构化结果，请重试")
        return items

    # ---- 08 生成与导出 ----

    async def generate_resume(
        self,
        db: DBSession,
        user_id: int,
        req: WizardGenerateRequest,
        llm: Any,
    ) -> tuple[dict[str, Any], Any | None, Any | None]:
        """组装（可选润色）向导内容，必要时导入简历库。

        Returns:
            (content, document, version) —— content 为 ResumeContent 形态字典。
        """
        content = self._assemble_content(req)
        if req.polish:
            try:
                content = await self._polish_content(content, llm)
            except Exception as e:  # 润色失败不阻塞生成，回退原内容
                logger.warning(f"[Wizard] 润色失败，使用原始组装内容: {e}")

        doc = version = None
        if req.import_to_library:
            doc, version = self._import_to_library(db, user_id, req, content)
        return content, doc, version

    # ---- 06 证件照 ----

    def upload_photo(
        self,
        db: DBSession,
        user_id: int,
        filename: str,
        content: bytes,
        upload_dir: str | None = None,
    ) -> ResumePhoto:
        surname = Path(filename or "photo.jpg").suffix.lower()
        if surname not in ALLOWED_PHOTO_SUFFIXES:
            raise WizardError(f"不支持的证件照格式: {surname}，允许 {sorted(ALLOWED_PHOTO_SUFFIXES)}")
        base = Path(upload_dir or settings.upload_dir)
        base.mkdir(parents=True, exist_ok=True)
        save_path = base / f"resume_photo_{user_id}_{uuid.uuid4().hex[:8]}{surname}"
        save_path.write_bytes(content)

        photo = (
            db.query(ResumePhoto).filter(ResumePhoto.user_id == user_id).first()
        )
        if photo is None:
            photo = ResumePhoto(
                user_id=user_id,
                filename=filename,
                file_path=str(save_path),
                mime_type=surname.lstrip("."),
            )
            db.add(photo)
        else:
            photo.filename = filename
            photo.file_path = str(save_path)
            photo.mime_type = surname.lstrip(".")
        db.commit()
        db.refresh(photo)
        return photo

    def get_photo(self, db: DBSession, user_id: int) -> ResumePhoto | None:
        return (
            db.query(ResumePhoto).filter(ResumePhoto.user_id == user_id).first()
        )

    @staticmethod
    def serialize_photo(photo: ResumePhoto | None) -> dict[str, Any] | None:
        if photo is None:
            return None
        return {
            "id": photo.id,
            "filename": photo.filename,
            "url": f"/api/resume-generation/photo/file?id={photo.id}",
            "created_at": photo.created_at,
        }

    # ---- 内部：组装 / 润色 / 导入 ----

    @staticmethod
    def _assemble_content(req: WizardGenerateRequest) -> dict[str, Any]:
        basic = req.basic_info or {}
        soft = req.soft_info or {}
        sections: list[dict[str, str]] = []

        # 01 基础信息 → 基本信息
        info_lines: list[str] = []
        for key, label in (
            ("name", "姓名"), ("email", "邮箱"), ("phone", "电话"),
            ("location", "所在地"), ("birthday", "出生日期"), ("gender", "性别"),
        ):
            value = basic.get(key)
            if value:
                info_lines.append(f"{label}：{value}")
        if info_lines:
            sections.append({"title": "基本信息", "content": "\n".join(info_lines)})

        # 02 方向 → 求职意向
        if req.directions:
            sections.append({"title": "求职意向", "content": "，".join(req.directions)})

        # 教育背景
        edu = basic.get("education")
        if edu:
            edu_text = "\n".join(str(e) for e in edu) if isinstance(edu, list) else str(edu)
            sections.append({"title": "教育背景", "content": edu_text.strip()})

        # 03/04 经历 → 实习/工作经历 + 项目经历
        work_blocks: list[str] = []
        project_blocks: list[str] = []
        for exp in req.experiences:
            block = ResumeWizardService._format_experience(exp)
            if exp.exp_type in ("实习", "工作", "职场"):
                work_blocks.append(block)
            else:
                project_blocks.append(block)
        if work_blocks:
            sections.append({"title": "实习/工作经历", "content": "\n\n".join(work_blocks)})
        if project_blocks:
            sections.append({"title": "项目经历", "content": "\n\n".join(project_blocks)})

        # 05 软性信息 → 技能 + 自我评价
        skills = soft.get("skills") or basic.get("skills") or []
        if skills:
            skill_text = ", ".join(str(s) for s in skills) if isinstance(skills, list) else str(skills)
            sections.append({"title": "技能", "content": skill_text.strip()})
        self_eval = soft.get("self_eval")
        if self_eval:
            sections.append({"title": "自我评价", "content": str(self_eval).strip()})

        # 证书/荣誉
        certs = basic.get("certifications")
        if certs:
            cert_text = "\n".join(str(c) for c in certs) if isinstance(certs, list) else str(certs)
            sections.append({"title": "证书/荣誉", "content": cert_text.strip()})

        # 07 模块顺序重排（未知标题按默认位置兜底）
        order = [t for t in (req.module_order or DEFAULT_MODULE_ORDER) if t]
        if order:
            sections.sort(
                key=lambda s: (
                    order.index(s["title"]) if s["title"] in order else len(order),
                    s["title"],
                )
            )

        raw_text = "\n\n".join(f"## {s['title']}\n{s['content']}" for s in sections)
        return {"sections": sections, "raw_text": raw_text}

    @staticmethod
    def _format_experience(exp: StarResultItem) -> str:
        parts = ["### " + " | ".join([x for x in (exp.company, exp.title) if x]).strip(" |")]
        for label, value in (("情境", exp.situation), ("任务", exp.task), ("行动", exp.action), ("结果", exp.result)):
            if value:
                parts.append(f"- {label}：{value}")
        return "\n".join(parts)

    async def _polish_content(self, content: dict[str, Any], llm: Any) -> dict[str, Any]:
        from app.llm.structured import ainvoke_json_with_schema

        result = await ainvoke_json_with_schema(
            llm,
            system_prompt=POLISH_SYSTEM_PROMPT,
            user_content=json.dumps(content, ensure_ascii=False),
            schema=ResumeContent,
            max_attempts=2,
            temperature=0.5,
            max_tokens=3072,
        )
        return {
            "sections": [{"title": s.title, "content": s.content} for s in result.sections],
            "raw_text": result.raw_text,
        }

    def _import_to_library(
        self,
        db: DBSession,
        user_id: int,
        req: WizardGenerateRequest,
        content: dict[str, Any],
    ) -> tuple[Any, Any]:
        from app.models.schemas import ResumeDocumentCreate, ResumeVersionCreate
        from app.services.resume_library_service import ResumeLibraryService

        lib = ResumeLibraryService()
        doc = lib.create_document(
            db,
            user_id,
            ResumeDocumentCreate(title=req.title, source="generation"),
        )
        version = lib.add_version(
            db,
            user_id,
            doc.id,
            ResumeVersionCreate(
                content=content,
                page_preference=req.page_preference,
            ),
        )
        return doc, version
