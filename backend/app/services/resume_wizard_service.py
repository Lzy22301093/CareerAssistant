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
    ExperienceDraftItem,
    ExperienceGenerateRequest,
    ExperienceStructureRequest,
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
    "你是专业中文简历润色助手。请润色给定模块正文：统一语感、表达更专业有力、"
    "在不改变事实与条目数量的前提下改善措辞。\n"
    "禁止使用 Markdown 语法（不要 #、**、- 列表符号），保持纯文本与原有换行结构。\n"
    "硬性约束：输出不得超过原文 1.15 倍长度；自我评价/个人优势不超过 120 字；禁止捏造事实。\n"
    "只输出 JSON：{\"content\":\"润色后的纯文本\"}，不要输出标题，不要增删模块。"
)

EXPERIENCE_FIELDS_DOC = (
    "每条经历字段：exp_type（项目|实习|竞赛|课程|校园）、company（公司/项目/机构）、"
    "title（角色）、duration（时间，如 2024.06-2024.09）、duty（职责，做了什么，专业润色）、"
    "achievement（成果/收获，尽量量化或写实）。"
)

STRUCTURE_SYSTEM_PROMPT = (
    "你是简历经历结构化与润色专家。用户会用自然语言粗略描述一段或多段实践经历。\n"
    "请：1）拆成 1~5 条独立经历；2）填全字段并优化措辞（duty/achievement 更专业有力，不捏造事实）；"
    "3）时间若原文有则保留，没有则留空。\n"
    + EXPERIENCE_FIELDS_DOC
    + "\n只输出 JSON：{\"items\":[{...}]}，不要任何额外文字。"
)

GENERATE_SYSTEM_PROMPT = (
    "你是简历经历包装专家。用户可能没有完整经历素材，请结合画像与投递方向，"
    "生成真实可写、便于继续完善的实践经历草稿（校园/项目/竞赛/课程/实习均可）。\n"
    "要求：基于画像中已有事实外推合理情节，不虚构不存在的公司名或奖项级别；"
    "duty/achievement 写得具体、可量化优先。\n"
    + EXPERIENCE_FIELDS_DOC
    + "\n只输出 JSON：{\"items\":[{...}]}，不要任何额外文字。"
)


class WizardError(ValueError):
    """生成区业务错误。"""


def _experience_batch_schema() -> type:
    """延迟构造经历批量输出 schema，避免循环导入。"""
    from pydantic import BaseModel, Field

    class ExperienceBatch(BaseModel):
        items: list[ExperienceDraftItem] = Field(default_factory=list)

    return ExperienceBatch


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

    # ---- 03 经历补充：自然语言结构化 / AI 生成 ----

    async def structure_experiences(
        self,
        db: DBSession,
        user_id: int,
        req: ExperienceStructureRequest,
        llm: Any,
    ) -> list[ExperienceDraftItem]:
        """把自然语言粗略描述结构化并润色为经历列表。"""
        text = (req.text or "").strip()
        if not text:
            raise WizardError("请先填写一段经历描述")

        from app.llm.structured import ainvoke_json_with_schema

        direction_line = "投递方向：" + "、".join(req.directions) if req.directions else ""
        profile_brief = self._profile_brief(db, user_id)
        user_content = (
            (f"候选人画像摘要：\n{profile_brief}\n\n" if profile_brief else "")
            + (direction_line + "\n\n" if direction_line else "")
            + "用户粗略描述：\n"
            + text
        )
        result = await ainvoke_json_with_schema(
            llm,
            system_prompt=STRUCTURE_SYSTEM_PROMPT,
            user_content=user_content,
            schema=_experience_batch_schema(),
            max_attempts=2,
            temperature=0.3,
            max_tokens=2048,
        )
        items = self._normalize_experience_items(result.items)
        if not items:
            raise WizardError("未能从描述中结构化出有效经历，请补充细节后重试")
        return items

    async def generate_experiences(
        self,
        db: DBSession,
        user_id: int,
        req: ExperienceGenerateRequest,
        llm: Any,
    ) -> list[ExperienceDraftItem]:
        """无经历时，按画像与方向生成经历草稿。"""
        from app.llm.structured import ainvoke_json_with_schema

        profile_brief = self._profile_brief(db, user_id)
        direction_line = "投递方向：" + "、".join(req.directions) if req.directions else ""
        user_content = (
            (f"候选人画像摘要：\n{profile_brief}\n\n" if profile_brief else "候选人画像摘要：（空）\n\n")
            + (direction_line + "\n" if direction_line else "")
            + f"请生成 {req.count} 条实践经历草稿。"
        )
        result = await ainvoke_json_with_schema(
            llm,
            system_prompt=GENERATE_SYSTEM_PROMPT,
            user_content=user_content,
            schema=_experience_batch_schema(),
            max_attempts=2,
            temperature=0.5,
            max_tokens=2048,
        )
        items = self._normalize_experience_items(result.items)[: req.count]
        if not items:
            raise WizardError("AI 未生成有效经历，请完善知识库画像后重试")
        return items

    def _profile_brief(self, db: DBSession, user_id: int) -> str:
        """压缩画像为 brief 文本，供经历包装/生成使用。"""
        from app.services.profile_service import build_profile_context

        ctx = build_profile_context(db, user_id)
        if not ctx:
            return ""
        parts: list[str] = []
        for key in ("name", "summary", "skills", "experience", "education", "target_roles", "certifications"):
            val = ctx.get(key)
            if not val:
                continue
            if isinstance(val, list):
                text_items = []
                for x in val:
                    if isinstance(x, dict):
                        text_items.append(f"{x.get('title', '')}: {x.get('content', '')}".strip(": "))
                    else:
                        text_items.append(str(x))
                parts.append(f"{key}: {'；'.join(text_items[:12])}")
            else:
                parts.append(f"{key}: {val}")
        return "\n".join(parts)

    def _normalize_experience_items(self, items: list[Any]) -> list[ExperienceDraftItem]:
        out: list[ExperienceDraftItem] = []
        for raw in items or []:
            exp_type = (getattr(raw, "exp_type", None) or "项目").strip() or "项目"
            if exp_type not in {"项目", "实习", "竞赛", "课程", "校园"}:
                exp_type = "项目"
            out.append(
                ExperienceDraftItem(
                    exp_type=exp_type,
                    company=(getattr(raw, "company", None) or "").strip(),
                    title=(getattr(raw, "title", None) or "").strip(),
                    duration=(getattr(raw, "duration", None) or "").strip(),
                    duty=(getattr(raw, "duty", None) or "").strip(),
                    achievement=(getattr(raw, "achievement", None) or "").strip(),
                    situation=(getattr(raw, "situation", None) or "").strip(),
                    task=(getattr(raw, "task", None) or "").strip(),
                    action=(getattr(raw, "action", None) or "").strip(),
                    result=(getattr(raw, "result", None) or "").strip(),
                )
            )
        return out

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
                duration=getattr(item, "duration", None),
                situation=(item.situation or "").strip(),
                task=(item.task or "").strip(),
                action=(item.action or "").strip(),
                result=(item.result or "").strip(),
                duty=getattr(item, "duty", None),
                achievement=getattr(item, "achievement", None),
            )
            if not any([star.situation, star.task, star.action, star.result]):
                original = by_key.get((star.exp_type, star.company, star.title))
                if original:
                    star.action = original.duty or ""
                    star.result = original.achievement or ""
                    star.duration = star.duration or original.duration
            items.append(star)
        if not items:
            raise WizardError("经历未生成有效的 STAR 结构化结果，请重试")
        return items

    # ---- 08 生成与导出 ----

    @staticmethod
    def default_resume_title(name: str | None, directions: list[str] | None) -> str:
        """默认标题：{姓名}·{主方向}简历。"""
        name = (name or "").strip()
        primary = (directions[0].strip() if directions else "") or ""
        if name and primary:
            return f"{name}·{primary}简历"
        if name:
            return f"{name}的简历"
        if primary:
            return f"{primary}简历"
        return "个人简历"

    async def generate_resume(
        self,
        db: DBSession,
        user_id: int,
        req: WizardGenerateRequest,
        llm: Any,
    ) -> tuple[dict[str, Any], Any | None, Any | None]:
        """按模板组装（可选润色）向导内容，必要时导入简历库。"""
        title = (req.title or "").strip()
        if not title or title in {"我的新简历", "我的简历", "简历"}:
            title = self.default_resume_title(
                (req.basic_info or {}).get("name"),
                req.directions,
            )
            req = req.model_copy(update={"title": title})

        from app.services.resume_template import assemble_with_template

        assembled = assemble_with_template(
            basic=req.basic_info or {},
            directions=req.directions or [],
            educations=list(req.educations or []),
            skills=list(req.skills or []),
            internships=list(req.internships or []),
            projects=list(req.projects or []),
            experiences=list(req.experiences or []),
            soft=req.soft_info or {},
            template_key=req.template,
            page_preference=req.page_preference,
        )
        content = assembled.to_content()
        if req.module_order:
            order = [t for t in req.module_order if t]
            content["sections"] = sorted(
                content["sections"],
                key=lambda s: (
                    order.index(s["title"]) if s["title"] in order else len(order),
                    s["title"],
                ),
            )
            content["raw_text"] = "\n\n".join(
                f"{s['title']}\n{s['content']}" for s in content["sections"]
            )

        if req.polish:
            try:
                content = await self._polish_content(content, llm)
            except Exception as e:
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
    def _merge_self_eval(soft: dict[str, Any]) -> str:
        """软性信息只并入自我评价，简历上不出现独立「软性信息」模块。"""
        parts: list[str] = []
        for key in ("self_eval", "personality", "vision"):
            val = (soft.get(key) or "").strip() if isinstance(soft.get(key), str) else ""
            if val and val not in parts:
                parts.append(val)
        # 不感兴趣方向不进简历正文
        return "\n".join(parts)

    @staticmethod
    def _assemble_content(req: WizardGenerateRequest) -> dict[str, Any]:
        """把向导数据组装成完整简历 sections（纯文本，无 Markdown）。"""
        basic = req.basic_info or {}
        soft = req.soft_info or {}
        sections: list[dict[str, str]] = []

        # 01 基础信息
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
            if edu_text.strip():
                sections.append({"title": "教育背景", "content": edu_text.strip()})

        # 03/04 经历 → 实习/工作 + 项目（含时间/职责/成果/STAR，纯文本）
        work_blocks: list[str] = []
        project_blocks: list[str] = []
        for exp in req.experiences:
            block = ResumeWizardService._format_experience(exp)
            if not block.strip():
                continue
            if exp.exp_type in ("实习", "工作", "职场"):
                work_blocks.append(block)
            else:
                project_blocks.append(block)
        if work_blocks:
            sections.append({"title": "实习/工作经历", "content": "\n\n".join(work_blocks)})
        if project_blocks:
            sections.append({"title": "项目经历", "content": "\n\n".join(project_blocks)})

        # 技能
        skills = soft.get("skills") or basic.get("skills") or []
        if skills:
            skill_text = "、".join(str(s).strip() for s in skills if str(s).strip()) if isinstance(skills, list) else str(skills)
            if skill_text.strip():
                sections.append({"title": "技能", "content": skill_text.strip()})

        # 自我评价（软性信息合并，无独立软性信息模块）
        self_eval = ResumeWizardService._merge_self_eval(soft)
        if self_eval:
            sections.append({"title": "自我评价", "content": self_eval})

        # 证书/荣誉
        certs = basic.get("certifications")
        if certs:
            cert_text = "\n".join(str(c) for c in certs if str(c).strip()) if isinstance(certs, list) else str(certs)
            if cert_text.strip():
                sections.append({"title": "证书/荣誉", "content": cert_text.strip()})

        # 07 模块顺序（仅排序，不丢模块）
        order = [t for t in (req.module_order or DEFAULT_MODULE_ORDER) if t]
        if order:
            sections.sort(
                key=lambda s: (
                    order.index(s["title"]) if s["title"] in order else len(order),
                    s["title"],
                )
            )

        raw_text = "\n\n".join(f"{s['title']}\n{s['content']}" for s in sections)
        return {"sections": sections, "raw_text": raw_text}

    @staticmethod
    def _format_experience(exp: StarResultItem) -> str:
        """经历块：纯文本，无 Markdown。"""
        header = " | ".join(
            x for x in (exp.company, exp.title, exp.duration) if x and str(x).strip()
        )
        lines: list[str] = []
        if header:
            lines.append(header)
        duty = (exp.duty or "").strip()
        if not duty:
            # STAR 后 action 常承载职责描述
            duty = (exp.action or "").strip()
        if duty:
            lines.append(f"职责：{duty}")
        for label, value in (
            ("情境", exp.situation),
            ("任务", exp.task),
            ("行动", exp.action),
            ("成果", exp.result or exp.achievement),
        ):
            value = (value or "").strip()
            if not value:
                continue
            if label in ("行动", "任务") and duty and value == duty:
                continue
            lines.append(f"{label}：{value}")
        if len(lines) == 1 and (exp.achievement or "").strip():
            lines.append(f"成果：{(exp.achievement or '').strip()}")
        return "\n".join(lines).strip()

    async def _polish_content(self, content: dict[str, Any], llm: Any) -> dict[str, Any]:
        """逐模块润色：禁止扩写；自我评价/个人优势硬截断。"""
        from app.llm.structured import ainvoke_json_with_schema
        from app.services.resume_template import clamp_text
        from pydantic import BaseModel, Field

        class PolishOne(BaseModel):
            content: str = Field(default="")

        polished_sections: list[dict[str, str]] = []
        for sec in content.get("sections") or []:
            title = str(sec.get("title") or "").strip()
            body = str(sec.get("content") or "")
            if not body.strip() or title == "基本信息":
                polished_sections.append({"title": title, "content": body})
                continue
            try:
                result = await ainvoke_json_with_schema(
                    llm,
                    system_prompt=POLISH_SYSTEM_PROMPT,
                    user_content=f"模块标题：{title}\n原始正文：\n{body}",
                    schema=PolishOne,
                    max_attempts=2,
                    temperature=0.3,
                    max_tokens=1024,
                )
                new_body = (result.content or "").strip()
                if not new_body:
                    new_body = body
                # 长度钳制：不超过原文 1.15 倍
                max_len = max(len(body), 20) * 115 // 100
                if len(new_body) > max_len:
                    new_body = clamp_text(new_body, max_len)
                if title in ("自我评价", "个人优势"):
                    new_body = clamp_text(new_body, 120)
                polished_sections.append({"title": title, "content": new_body})
            except Exception as e:
                logger.warning(f"[Wizard] 模块「{title}」润色失败，保留原文: {e}")
                polished_sections.append({"title": title, "content": body})

        raw_text = "\n\n".join(f"{s['title']}\n{s['content']}" for s in polished_sections)
        return {"sections": polished_sections, "raw_text": raw_text}

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
