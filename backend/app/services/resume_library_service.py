"""ResumeLibraryService — 简历库资产（阶段2 指令2-1）。

文档（ResumeDocument）+ 多版本（ResumeVersion）+ 区域（ResumeSection）+ 回收站。
方法接收 db（Session），便于在测试中用 SQLite 注入。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import AnalysisSession, ResumeDocument, ResumeSection, ResumeVersion
from app.models.schemas import (
    ResumeDocumentCreate,
    ResumeDocumentUpdate,
    ResumeSectionUpdate,
    ResumeVersionCreate,
)

logger = logging.getLogger(__name__)

ALLOWED_SOURCES = {"manual", "session", "upload", "generation"}
ALLOWED_SECTION_TYPES = {
    "header",
    "summary",
    "objective",  # 求职意向（生成区模块）
    "education",
    "experience",
    "project",
    "skill",
    "certification",
    "custom",
}

# 区块标题关键词 → section_type（用于从聊天产物自动生成区域）
_TITLE_TYPE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("教育", "学历"), "education"),
    (("工作经历", "实习", "职业经历", "工作"), "experience"),
    (("项目",), "project"),
    (("技能",), "skill"),
    (("证书", "资格"), "certification"),
    (("自我评价", "个人总结", "总结", "简介", "概述"), "summary"),
    (("基本信息", "联系方式", "个人信息"), "header"),
    (("求职意向", "意向", "目标岗位", "目标方向"), "objective"),
]


class ResumeLibraryError(ValueError):
    """业务校验错误。"""


def _ensure(value: str | None, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise ResumeLibraryError(f"{label} 非法: {value!r}，允许 {sorted(allowed)}")
    return value


def parse_json_object(raw: str | None) -> dict[str, Any] | None:
    """安全解析 JSON 对象，失败返回 None（脏数据不炸接口）。"""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def infer_section_type(title: str | None) -> str:
    """根据区块标题推断 section_type，未命中归为 custom。"""
    if not title:
        return "custom"
    for keywords, section_type in _TITLE_TYPE_KEYWORDS:
        if any(k in title for k in keywords):
            return section_type
    return "custom"


# 上传导入的标题行关键词提示（保守判据，尽量不误判正文行）
_UPLOAD_HEADING_HINTS = (
    "教育", "学历", "经历", "项目", "技能", "证书", "自我评价", "个人总结",
    "基本信息", "求职意向", "荣誉", "获奖", "奖项", "实习", "工作", "简介", "概况",
    "联系方式", "个人信息", "特长", "语言",
)


def sections_from_text(text: str) -> dict[str, Any]:
    """把纯文本简历启发式拆成"标题行 + 正文块"的 sections（上传导入用）。

    标题判据：短行（≤30 字符）+ 不以句号/冒号等标点结尾 + 不以列表符号开头 + 不含 |
    + 行中包含常见板块关键词（教育/经历/技能/证书/自我评价等）。
    无标题命中时整体作为"正文"单块。
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        is_heading = (
            len(line) <= 30
            and not line.endswith(("。", "：", "，", ";", "；", ",", "!", "？"))
            and not line.startswith(("-", "•", "·", "*"))
            and "|" not in line
            and any(k in line for k in _UPLOAD_HEADING_HINTS)
        )
        if is_heading:
            current = {"title": line, "content": []}
            blocks.append(current)
        else:
            if current is None:
                current = {"title": None, "content": []}
                blocks.append(current)
            current["content"].append(line)
    sections: list[dict[str, Any]] = []
    for block in blocks:
        content = "\n".join(block["content"]).strip()
        if not content:
            continue
        sections.append({"title": block["title"] or "正文", "content": content})
    if not sections:
        sections = [{"title": "正文", "content": text.strip()}]
    return {"sections": sections, "raw_text": text}


def _sections_from_content(content: Mapping[str, Any]) -> list[dict[str, Any]]:
    """把 ResumeContent 形态的 content 拆成区域行数据（页码从 1 顺排，boundingBox 由前端框选后回填）。"""
    sections: list[dict[str, Any]] = []
    raw_sections = content.get("sections")
    if isinstance(raw_sections, list):
        for idx, sec in enumerate(raw_sections):
            if not isinstance(sec, Mapping):
                continue
            title = str(sec.get("title") or "").strip() or None
            sections.append(
                {
                    "page_number": int(sec.get("page_number") or 1),
                    "section_type": str(sec.get("section_type") or "") or infer_section_type(title),
                    "title": title,
                    "content": sec.get("content"),
                    "sort_order": idx,
                }
            )
    if not sections:
        raw_text = str(content.get("raw_text") or "").strip()
        if raw_text:
            sections.append(
                {
                    "page_number": 1,
                    "section_type": "custom",
                    "title": None,
                    "content": raw_text,
                    "sort_order": 0,
                }
            )
    for sec in sections:
        if sec["section_type"] not in ALLOWED_SECTION_TYPES:
            sec["section_type"] = "custom"
    return sections


class ResumeLibraryService:
    """简历文档 + 版本 + 区域 + 回收站。"""

    # ---- 文档 ----

    def create_document(self, db: DBSession, user_id: int, data: ResumeDocumentCreate) -> ResumeDocument:
        _ensure(data.source, ALLOWED_SOURCES, "source")
        doc = ResumeDocument(user_id=user_id, title=data.title, source=data.source, notes=data.notes)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    def list_documents(self, db: DBSession, user_id: int, include_deleted: bool = False) -> list[ResumeDocument]:
        q = db.query(ResumeDocument).filter(ResumeDocument.user_id == user_id)
        if not include_deleted:
            q = q.filter(ResumeDocument.deleted_at.is_(None))
        return q.order_by(ResumeDocument.updated_at.desc(), ResumeDocument.id.desc()).all()

    def list_deleted(self, db: DBSession, user_id: int) -> list[ResumeDocument]:
        """回收站列表。"""
        return (
            db.query(ResumeDocument)
            .filter(ResumeDocument.user_id == user_id, ResumeDocument.deleted_at.isnot(None))
            .order_by(ResumeDocument.deleted_at.desc())
            .all()
        )

    def get_document(self, db: DBSession, user_id: int, doc_id: int, include_deleted: bool = False) -> ResumeDocument:
        doc = db.query(ResumeDocument).filter(ResumeDocument.id == doc_id, ResumeDocument.user_id == user_id).first()
        if doc is None or (doc.deleted_at is not None and not include_deleted):
            raise ResumeLibraryError("简历文档不存在")
        return doc

    def rename_document(self, db: DBSession, user_id: int, doc_id: int, data: ResumeDocumentUpdate) -> ResumeDocument:
        doc = self.get_document(db, user_id, doc_id, include_deleted=True)
        updates = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in updates.items():
            setattr(doc, field, value)
        db.commit()
        db.refresh(doc)
        return doc

    def soft_delete_document(self, db: DBSession, user_id: int, doc_id: int) -> ResumeDocument:
        """移入回收站（软删除，可恢复）。"""
        doc = self.get_document(db, user_id, doc_id)
        doc.deleted_at = datetime.now()
        db.commit()
        db.refresh(doc)
        return doc

    def restore_document(self, db: DBSession, user_id: int, doc_id: int) -> ResumeDocument:
        doc = self.get_document(db, user_id, doc_id, include_deleted=True)
        doc.deleted_at = None
        db.commit()
        db.refresh(doc)
        return doc

    def purge_document(self, db: DBSession, user_id: int, doc_id: int) -> None:
        """彻底删除（版本与区域级联清除，不可恢复）。"""
        doc = self.get_document(db, user_id, doc_id, include_deleted=True)
        db.delete(doc)
        db.commit()

    # ---- 版本 ----

    def add_version(self, db: DBSession, user_id: int, doc_id: int, data: ResumeVersionCreate) -> ResumeVersion:
        """新增一版简历内容：版本号在文档内自增，自动拆分区域，并设为当前版本。"""
        doc = self.get_document(db, user_id, doc_id)
        max_version = (
            db.query(ResumeVersion.version)
            .filter(ResumeVersion.document_id == doc.id)
            .order_by(ResumeVersion.version.desc())
            .first()
        )
        version = ResumeVersion(
            document_id=doc.id,
            user_id=user_id,
            version=(max_version[0] + 1) if max_version else 1,
            content_json=json.dumps(data.content, ensure_ascii=False),
            render_config_json=json.dumps(
                {**(data.render_config or {}), "page_preference": data.page_preference},
                ensure_ascii=False,
            ),
        )
        db.add(version)
        db.flush()
        for sec in _sections_from_content(data.content):
            db.add(ResumeSection(resume_version_id=version.id, **sec))
        doc.current_version_id = version.id
        db.commit()
        db.refresh(version)
        return version

    def list_versions(self, db: DBSession, user_id: int, doc_id: int) -> list[ResumeVersion]:
        doc = self.get_document(db, user_id, doc_id, include_deleted=True)
        return (
            db.query(ResumeVersion)
            .filter(ResumeVersion.document_id == doc.id)
            .order_by(ResumeVersion.version.desc())
            .all()
        )

    def get_version(self, db: DBSession, user_id: int, version_id: int) -> ResumeVersion:
        version = (
            db.query(ResumeVersion)
            .join(ResumeDocument, ResumeVersion.document_id == ResumeDocument.id)
            .filter(ResumeVersion.id == version_id, ResumeDocument.user_id == user_id)
            .first()
        )
        if version is None:
            raise ResumeLibraryError("简历版本不存在")
        return version

    def set_page_preference(
        self, db: DBSession, user_id: int, version_id: int, page_preference: str
    ) -> ResumeVersion:
        """更新版本的页数偏好（阶段3 3-2：多页数导出；写入 render_config.page_preference）。"""
        if page_preference not in {"one_page", "two_pages"}:
            raise ResumeLibraryError(f"page_preference 非法: {page_preference!r}")
        version = self.get_version(db, user_id, version_id)
        rc = parse_json_object(version.render_config_json) or {}
        rc["page_preference"] = page_preference
        version.render_config_json = json.dumps(rc, ensure_ascii=False)
        db.commit()
        db.refresh(version)
        return version

    def rollback_version(self, db: DBSession, user_id: int, doc_id: int, version_id: int) -> ResumeDocument:
        """回滚 = 把文档当前版本指针指回历史版本（非破坏性，版本历史完整保留）。"""
        doc = self.get_document(db, user_id, doc_id)
        version = self.get_version(db, user_id, version_id)
        if version.document_id != doc.id:
            raise ResumeLibraryError("该版本不属于此简历文档")
        doc.current_version_id = version.id
        db.commit()
        db.refresh(doc)
        return doc

    # ---- 区域 ----

    def list_sections(self, db: DBSession, user_id: int, version_id: int) -> list[ResumeSection]:
        version = self.get_version(db, user_id, version_id)
        return (
            db.query(ResumeSection)
            .filter(ResumeSection.resume_version_id == version.id)
            .order_by(ResumeSection.sort_order.asc(), ResumeSection.id.asc())
            .all()
        )

    def get_section(self, db: DBSession, user_id: int, section_id: int) -> ResumeSection:
        section = (
            db.query(ResumeSection)
            .join(ResumeVersion, ResumeSection.resume_version_id == ResumeVersion.id)
            .join(ResumeDocument, ResumeVersion.document_id == ResumeDocument.id)
            .filter(ResumeSection.id == section_id, ResumeDocument.user_id == user_id)
            .first()
        )
        if section is None:
            raise ResumeLibraryError("简历区域不存在")
        return section

    def update_section(self, db: DBSession, user_id: int, section_id: int, data: ResumeSectionUpdate) -> ResumeSection:
        section = self.get_section(db, user_id, section_id)
        raw = data.model_dump(exclude_unset=True)
        # bounding_box 显式传 null 表示清除选框；其它字段仍用 exclude_none 防误清空
        box_explicit = "bounding_box" in raw
        bounding = raw.pop("bounding_box", None)
        updates = {k: v for k, v in raw.items() if v is not None}
        if "section_type" in updates:
            _ensure(updates["section_type"], ALLOWED_SECTION_TYPES, "section_type")
        for field, value in updates.items():
            setattr(section, field, value)
        if box_explicit:
            section.bounding_box = (
                json.dumps(bounding, ensure_ascii=False) if bounding is not None else None
            )
        db.commit()
        db.refresh(section)
        return section

    # ---- 区域改写采纳（阶段2 指令2-2/2-3） ----

    def adopt_section_rewrite(
        self,
        db: DBSession,
        user_id: int,
        version_id: int,
        section_id: int,
        new_content: str,
    ) -> ResumeVersion:
        """采纳区域改写：生成一个新版本（目标区域替换为改写文本），保留旧版本可回滚。

        新版本的区域行继承旧版的全部元数据（page/bounding_box/sort_order），
        仅目标区域 content 替换；content_json 同步替换对应条目并重算 raw_text。
        """
        version = self.get_version(db, user_id, version_id)
        section = self.get_section(db, user_id, section_id)
        if section.resume_version_id != version.id:
            raise ResumeLibraryError("该区域不属于此版本")

        content = parse_json_object(version.content_json) or {"sections": [], "raw_text": version.content_json}
        sections = content.get("sections")
        replaced = False
        if isinstance(sections, list):
            # 优先按 sort_order 索引命中（区域行即按顺序从 content 生成）
            if 0 <= section.sort_order < len(sections):
                target = sections[section.sort_order]
                if isinstance(target, dict) and (not section.title or (target.get("title") or None) == section.title):
                    target["content"] = new_content
                    replaced = True
            if not replaced:
                for sec in sections:
                    if isinstance(sec, dict) and sec.get("title") and sec.get("title") == section.title:
                        sec["content"] = new_content
                        replaced = True
                        break
            if not replaced:
                sections.append({"title": section.title, "content": new_content})
                replaced = True
        if not replaced:
            content["sections"] = [{"title": section.title, "content": new_content}]
        if content.get("raw_text") is not None:
            content["raw_text"] = "\n".join(
                str(s.get("content") or "") for s in content.get("sections", []) if isinstance(s, dict)
            )

        max_version = (
            db.query(ResumeVersion.version)
            .filter(ResumeVersion.document_id == version.document_id)
            .order_by(ResumeVersion.version.desc())
            .first()
        )
        new_version = ResumeVersion(
            document_id=version.document_id,
            session_id=version.session_id,
            user_id=user_id,
            version=(max_version[0] + 1) if max_version else 1,
            content_json=json.dumps(content, ensure_ascii=False),
            render_config_json=version.render_config_json,
        )
        db.add(new_version)
        db.flush()
        for old in version.sections:
            db.add(
                ResumeSection(
                    resume_version_id=new_version.id,
                    page_number=old.page_number,
                    section_type=old.section_type,
                    title=old.title,
                    content=new_content if old.id == section.id else old.content,
                    bounding_box=old.bounding_box,
                    sort_order=old.sort_order,
                )
            )
        if version.document is not None:
            version.document.current_version_id = new_version.id
        db.commit()
        db.refresh(new_version)
        return new_version

    # ---- 会话导入 ----

    def import_from_session(
        self,
        db: DBSession,
        user_id: int,
        session_id: str,
        title: str | None = None,
    ) -> tuple[ResumeDocument, ResumeVersion]:
        """把聊天会话最新一次生成的简历导入简历库（复制为独立版本，会话数据保持不动）。"""
        source_version = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.session_id == session_id)
            .order_by(ResumeVersion.created_at.desc(), ResumeVersion.id.desc())
            .first()
        )
        if source_version is None:
            raise ResumeLibraryError("该会话没有可导入的简历内容")
        if source_version.session and source_version.session.user_id not in (None, user_id):
            raise ResumeLibraryError("该会话不属于当前用户")
        doc = self.create_document(
            db,
            user_id,
            ResumeDocumentCreate(
                title=title or f"会话简历 {session_id[:8]}",
                source="session",
            ),
        )
        version = self.add_version(
            db,
            user_id,
            doc.id,
            ResumeVersionCreate(
                content=parse_json_object(source_version.content_json) or {"raw_text": source_version.content_json},
                render_config=parse_json_object(source_version.render_config_json),
            ),
        )
        return doc, version

    # ---- 上传 / 生成导入（生成区缺口） ----

    def import_generated(
        self,
        db: DBSession,
        user_id: int,
        title: str,
        content: dict[str, Any],
        page_preference: str = "one_page",
    ) -> tuple[ResumeDocument, ResumeVersion]:
        """把结构化简历内容导入简历库（生成区产物，source=generation）。"""
        doc = self.create_document(db, user_id, ResumeDocumentCreate(title=title, source="generation"))
        version = self.add_version(
            db,
            user_id,
            doc.id,
            ResumeVersionCreate(content=content, page_preference=page_preference),
        )
        return doc, version

    async def import_uploaded_file(
        self,
        db: DBSession,
        user_id: int,
        title: str,
        file_content_b64: str,
        filename: str,
    ) -> tuple[ResumeDocument, ResumeVersion]:
        """上传 Word/PDF/TXT/MD → 解析 → 启发式拆区域 → 导入简历库（source=upload）。"""
        from app.tools.file_tools import FileParserTool

        result = await FileParserTool().execute(file_content=file_content_b64, filename=filename)
        if not result.success:
            raise ResumeLibraryError(f"文件解析失败: {result.error}")
        text = (result.data.get("text") or "").strip()
        if not text:
            raise ResumeLibraryError("文件未提取到有效文本内容")
        content = sections_from_text(text)
        doc = self.create_document(db, user_id, ResumeDocumentCreate(title=title, source="upload"))
        version = self.add_version(db, user_id, doc.id, ResumeVersionCreate(content=content))
        # P0：落盘原件，供 Word 保版导出（不提供下载接口）
        try:
            import base64 as _b64

            from app.services.resume_docx_layout import ResumeSourceFileService

            raw = _b64.b64decode(file_content_b64)
            mime = ""
            low = (filename or "").lower()
            if low.endswith(".docx"):
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif low.endswith(".pdf"):
                mime = "application/pdf"
            ResumeSourceFileService().save_original(
                db, user_id, doc.id, filename or "resume.bin", raw, mime
            )
        except Exception as e:
            # 原件失败不阻断导入
            logger.warning(f"[ResumeLibrary] 保存上传原件失败 doc={doc.id}: {e}")
        return doc, version

    # ---- 会话辅助 ----

    @staticmethod
    def find_session(db: DBSession, user_id: int, session_id: str) -> AnalysisSession:
        session = (
            db.query(AnalysisSession)
            .filter(AnalysisSession.session_id == session_id, AnalysisSession.user_id == user_id)
            .first()
        )
        if session is None:
            raise ResumeLibraryError("分析会话不存在")
        return session
