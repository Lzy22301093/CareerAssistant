"""简历上传原件存储（P0）+ DOCX 保版导出（P1）。

- 上传时把原件落盘并挂到 resume_documents，供后续保版写回
- 导出 layout=preserve：打开原 DOCX，按当前区域文本替换匹配段落
- 匹配失败则抛 DocxLayoutError，由 API 让前端提示用户改用统一模板
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.models.orm import ResumeDocument, ResumeSection, ResumeSourceFile, ResumeVersion

logger = logging.getLogger(__name__)

_DOCX_SUFFIXES = {".docx"}


class DocxLayoutError(ValueError):
    """无法按原版式导出。"""


def _norm_text(s: str) -> str:
    """归一化用于匹配：去空白、全半角标点、常见装饰符。"""
    s = (s or "").strip()
    s = s.replace("　", " ")
    s = re.sub(r"\s+", "", s)
    for a, b in (
        ("（", "("), ("）", ")"),
        ("，", ","), ("。", "."),
        ("：", ":"), ("；", ";"),
        ("！", "!"), ("？", "?"),
        ("“", '"'), ("”", '"'),
        ("‘", "'"), ("’", "'"),
        ("–", "-"), ("—", "-"),
        ("•", "·"), ("●", "·"),
    ):
        s = s.replace(a, b)
    return s.lower()


class ResumeSourceFileService:
    """原件落盘 + 元数据。"""

    def save_original(
        self,
        db: DBSession,
        user_id: int,
        document_id: int,
        filename: str,
        content: bytes,
        mime_type: str = "",
    ) -> ResumeSourceFile:
        base = Path(settings.upload_dir) / "resume_originals"
        base.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename or "resume.bin").suffix.lower() or ".bin"
        if len(suffix) > 10:
            suffix = ".bin"
        sha = hashlib.sha256(content).hexdigest()
        path = base / f"resume_{user_id}_{document_id}_{uuid.uuid4().hex[:10]}{suffix}"
        path.write_bytes(content)

        row = (
            db.query(ResumeSourceFile)
            .filter(
                ResumeSourceFile.user_id == user_id,
                ResumeSourceFile.document_id == document_id,
            )
            .first()
        )
        if row is None:
            row = ResumeSourceFile(
                user_id=user_id,
                document_id=document_id,
                filename=filename or path.name,
                file_path=str(path),
                mime_type=mime_type or "",
                file_size=len(content),
                sha256=sha,
            )
            db.add(row)
        else:
            # 覆盖旧原件
            try:
                if row.file_path and Path(row.file_path).exists():
                    Path(row.file_path).unlink(missing_ok=True)
            except OSError:
                pass
            row.filename = filename or path.name
            row.file_path = str(path)
            row.mime_type = mime_type or row.mime_type
            row.file_size = len(content)
            row.sha256 = sha
        db.commit()
        db.refresh(row)
        return row

    def get_for_document(
        self, db: DBSession, user_id: int, document_id: int
    ) -> ResumeSourceFile | None:
        return (
            db.query(ResumeSourceFile)
            .filter(
                ResumeSourceFile.user_id == user_id,
                ResumeSourceFile.document_id == document_id,
            )
            .first()
        )

    def is_docx(self, row: ResumeSourceFile | None) -> bool:
        if row is None:
            return False
        return Path(row.filename or row.file_path).suffix.lower() in _DOCX_SUFFIXES


class DocxLayoutService:
    """原 DOCX + 当前区域文本 → 保版 Word 字节流。"""

    def export_preserve(
        self,
        db: DBSession,
        user_id: int,
        document_id: int,
        version_id: int | None = None,
    ) -> bytes:
        from app.services.resume_library_service import ResumeLibraryError, ResumeLibraryService

        lib = ResumeLibraryService()
        source_svc = ResumeSourceFileService()
        src = source_svc.get_for_document(db, user_id, document_id)
        if src is None or not source_svc.is_docx(src):
            raise DocxLayoutError("没有可用的 Word 原件，无法保排版导出")
        if not Path(src.file_path).exists():
            raise DocxLayoutError("原件文件已不存在，请重新上传或使用统一模板导出")

        try:
            doc = lib.get_document(db, user_id, document_id)
        except ResumeLibraryError as e:
            raise DocxLayoutError(str(e)) from e

        version: ResumeVersion | None = None
        if version_id:
            for v in doc.versions:
                if v.id == version_id:
                    version = v
                    break
        if version is None:
            target_id = doc.current_version_id
            if target_id:
                version = next((v for v in doc.versions if v.id == target_id), None)
            if version is None and doc.versions:
                version = max(doc.versions, key=lambda v: v.version or 0)
        if version is None:
            raise DocxLayoutError("简历没有版本内容")

        sections: list[ResumeSection] = list(version.sections or [])
        if not sections:
            raise DocxLayoutError("当前版本没有区域内容")

        return self._replace_paragraphs(src.file_path, sections)

    @staticmethod
    def _paragraph_texts(doc: Any) -> list[str]:
        return [p.text or "" for p in doc.paragraphs]

    @staticmethod
    def _set_paragraph_text(paragraph: Any, text: str) -> None:
        """替换段落文字：保留段落样式，run 尽量只改第一个，避免丢字体。"""
        if not paragraph.runs:
            paragraph.add_run(text)
            return
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""

    def _replace_paragraphs(self, path: str, sections: list[ResumeSection]) -> bytes:
        from docx import Document

        try:
            doc = Document(path)
        except Exception as e:
            raise DocxLayoutError(f"无法打开 Word 原件: {e}") from e

        paras = doc.paragraphs
        texts = self._paragraph_texts(doc)
        norm_paras = [_norm_text(t) for t in texts]
        occupied = [False] * len(paras)
        matched = 0
        total = 0

        for sec in sections:
            body = (sec.content or "").strip()
            if not body:
                continue
            total += 1
            # 区域全文归一化后作为整段目标；再尝试按行拆到连续段落
            lines = [ln for ln in body.splitlines() if ln.strip()]
            if not lines:
                continue

            # 1) 整段匹配：某段落归一化后等于/包含区域全文
            full_n = _norm_text(body)
            hit_idx: list[int] | None = None
            for i, np in enumerate(norm_paras):
                if occupied[i] or not np:
                    continue
                if np == full_n or (full_n and full_n in np and len(full_n) > 8):
                    hit_idx = [i]
                    break

            # 2) 多行连续匹配：第一行命中后向后吸收连续段
            if hit_idx is None:
                first_n = _norm_text(lines[0])
                if not first_n:
                    continue
                for i, np in enumerate(norm_paras):
                    if occupied[i] or not np:
                        continue
                    if first_n in np or np in first_n:
                        hit_idx = [i]
                        for j in range(i + 1, min(i + len(lines), len(paras))):
                            if occupied[j]:
                                break
                            ln_n = _norm_text(lines[j - i]) if (j - i) < len(lines) else ""
                            pj = norm_paras[j]
                            if not ln_n:
                                break
                            if ln_n in pj or pj in ln_n or not pj:
                                hit_idx.append(j)
                            else:
                                break
                        break

            if not hit_idx:
                continue

            # 写入：第一段放全文（按行），多余命中段清空
            self._set_paragraph_text(paras[hit_idx[0]], lines[0] if len(hit_idx) == 1 else lines[0])
            if len(hit_idx) == 1 and len(lines) > 1:
                # 单段承载多行：用换行写进同一段
                self._set_paragraph_text(paras[hit_idx[0]], "\n".join(lines))
            else:
                for k, idx in enumerate(hit_idx):
                    if k < len(lines):
                        self._set_paragraph_text(paras[idx], lines[k])
                    else:
                        self._set_paragraph_text(paras[idx], "")
            for idx in hit_idx:
                occupied[idx] = True
            matched += 1

        if matched == 0:
            raise DocxLayoutError("未能在原 Word 中定位任何区域文本，无法保排版导出")
        if total and matched < max(1, int(total * 0.4)):
            raise DocxLayoutError(
                f"仅匹配到 {matched}/{total} 个区域，原版式导出不可靠，请使用统一模板"
            )

        buf = io.BytesIO()
        doc.save(buf)
        data = buf.getvalue()
        if data[:2] != b"PK":
            raise DocxLayoutError("保版导出结果无效")
        return data
