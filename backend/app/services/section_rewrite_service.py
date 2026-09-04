"""SectionRewriteService — 区域改写编排（阶段2 指令2-2）。

上下文 = 当前版本 + 选中区域 + 画像事实（confirmed）+ 可选 JD + 历史对话；
输出多条候选改写；不覆盖原文（采纳走 resume_library_service.adopt_section_rewrite）。
捏造检测双保险：LLM 自报 new_numbers/new_claims + 代码级数字比对（确定性兜底）。
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session as DBSession

from app.agents.section_rewriter import SectionRewriterAgent
from app.models.orm import ResumeSection, ResumeVersion
from app.services.profile_service import build_profile_context
from app.services.rewrite_schema import SectionRewriteOutput
from app.services.resume_library_service import parse_json_object

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")

# 上下文裁剪上限（沿用 compact_* 的预算思想）
_SIBLING_MAX_SECTIONS = 15
_SIBLING_MAX_CHARS = 200
_HISTORY_MAX_ITEMS = 8
_HISTORY_MAX_CHARS = 500


class SectionRewriteError(ValueError):
    """区域改写业务错误（含 LLM 输出校验失败）。"""


def _numbers_in(text: str) -> set[str]:
    """提取文本中的数字词元（去掉小数点后尾随形式差异由 re.escape 精确比对）。"""
    return set(_NUM_RE.findall(text or ""))


def _find_fabricated_numbers(rewrite: str, corpus_numbers: set[str]) -> list[str]:
    """找出改写文本中出现、但事实语料中不存在的数字。"""
    return sorted(_numbers_in(rewrite) - corpus_numbers)


def _sibling_summary(version: ResumeVersion, exclude_sort_order: int) -> str:
    """除选中区域外的整份简历摘要（限流裁剪，防上下文膨胀）。"""
    lines: list[str] = []
    sections = [s for s in version.sections if s.sort_order != exclude_sort_order]
    for sec in sections[:_SIBLING_MAX_SECTIONS]:
        content = (sec.content or "").strip()
        if len(content) > _SIBLING_MAX_CHARS:
            content = content[:_SIBLING_MAX_CHARS] + "…"
        lines.append(f"- {sec.title or '（无标题）'}: {content}" if content else f"- {sec.title or '（无标题）'}")
    return "\n".join(lines)


def _clean_history(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """清洗迭代对话历史：只留 role/content，截断超长项。"""
    cleaned: list[dict[str, str]] = []
    for item in (history or [])[-_HISTORY_MAX_ITEMS:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        cleaned.append({"role": role, "content": content[:_HISTORY_MAX_CHARS]})
    return cleaned


class SectionRewriteService:
    """区域改写：生成候选 + 捏造标记。"""

    def __init__(self, llm: Any = None):
        self._llm = llm

    def _get_llm(self) -> Any:
        if self._llm is None:
            from app.llm import create_llm_provider

            self._llm = create_llm_provider()
        return self._llm

    async def generate_candidates(
        self,
        db: DBSession,
        user_id: int,
        section_id: int,
        instruction: str,
        conversation_history: list[dict[str, Any]] | None = None,
        jd_analysis: dict[str, Any] | None = None,
        profile_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成改写候选。返回序列化结果，前端直接渲染 diff 与确认标记。"""
        section = self._get_section(db, user_id, section_id)
        version = section.resume_version
        if profile_context is None:
            profile_context = build_profile_context(db, user_id)

        agent = SectionRewriterAgent(self._get_llm())
        raw = await agent.run(
            section_title=section.title or "",
            section_type=section.section_type,
            section_text=section.content or "",
            resume_summary=_sibling_summary(version, section.sort_order),
            profile_context=profile_context,
            jd_analysis=jd_analysis,
            user_instruction=instruction,
            conversation_history=_clean_history(conversation_history),
        )
        try:
            output = SectionRewriteOutput.model_validate(raw)
        except ValidationError as e:
            raise SectionRewriteError(f"改写结果校验失败: {e.errors()[:3]}") from e

        # 代码级捏造比对：事实语料 = 区域原文 + 整版内容 + 画像事实（+ JD 文本）
        corpus = " ".join(
            filter(
                None,
                [
                    section.content or "",
                    version.content_json or "",
                    json.dumps(profile_context or {}, ensure_ascii=False),
                    json.dumps(jd_analysis or {}, ensure_ascii=False),
                ],
            )
        )
        corpus_numbers = _numbers_in(corpus)

        original_text = (section.content or "").strip()
        candidates: list[dict[str, Any]] = []
        all_new_numbers: set[str] = set(output.new_numbers)
        for cand in output.candidates:
            rewrite = (cand.rewrite or "").strip()
            if not rewrite or rewrite == original_text:
                continue  # 无效/未改动候选直接丢弃
            fabricated = _find_fabricated_numbers(rewrite, corpus_numbers)
            all_new_numbers.update(fabricated)
            candidates.append(
                {
                    "rewrite": rewrite,
                    "approach": cand.approach,
                    "changes": cand.changes,
                    "new_numbers": fabricated,
                }
            )
        if not candidates:
            raise SectionRewriteError("没有有效的改写候选，请调整指令后重试")

        all_new_numbers = {n for n in all_new_numbers if n not in corpus_numbers}
        new_claims = [c for c in output.new_claims if c]
        return {
            "section_id": section.id,
            "version_id": version.id,
            "candidates": candidates,
            "needs_source_confirmation": bool(all_new_numbers or new_claims),
            "new_numbers": sorted(all_new_numbers),
            "new_claims": new_claims,
            "advice": output.advice,
        }

    @staticmethod
    def _get_section(db: DBSession, user_id: int, section_id: int) -> ResumeSection:
        from app.services.resume_library_service import ResumeLibraryError, ResumeLibraryService

        try:
            return ResumeLibraryService().get_section(db, user_id, section_id)
        except ResumeLibraryError as e:
            raise SectionRewriteError(str(e)) from e
