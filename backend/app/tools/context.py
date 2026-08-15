"""上下文压缩工具 — 裁剪喂给 LLM 的 JSON 上下文，降低输入 token 与推理耗时。

性能优化 A4：
- profile 的 experience/projects 通常很长，全量塞进 prompt 会产生几万 token
- 下游 Agent（gap/content/review/interview）只关心核心信息，
  截断超长文本、限制列表条数即可显著压缩输入

所有函数都是纯函数，输入不被修改。
"""

from __future__ import annotations

from typing import Any


def _truncate_str(value: Any, max_chars: int = 400) -> str:
    """字符串截断（非字符串先转 str）。"""
    s = str(value)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "…"


def _truncate_list(items: list[Any], limit: int) -> list[Any]:
    """列表截断到前 limit 条。"""
    if len(items) <= limit:
        return list(items)
    return list(items[:limit]) + [{"_truncated": True, "count": len(items) - limit}]


def _trim_highlights(exp: dict[str, Any], max_highlights: int = 4, max_chars: int = 200) -> dict[str, Any]:
    """压缩单条经历/项目的 highlights。"""
    out = dict(exp)
    highlights = out.get("highlights") or []
    if isinstance(highlights, list):
        out["highlights"] = _truncate_list(highlights, max_highlights)
    for key in ("description", "summary"):
        if key in out and out[key]:
            out[key] = _truncate_str(out[key], max_chars)
    return out


def compact_profile(profile: dict[str, Any] | None, max_items: int = 5, max_chars: int = 400) -> dict[str, Any]:
    """压缩候选人画像。

    - experience / projects / education 各保留前 max_items 条
    - highlights 每条保留前 4 项、单条截断到 max_chars
    """
    if not profile:
        return {}

    out = dict(profile)
    for key, limit in (("experience", max_items), ("projects", max_items), ("education", max_items)):
        items = out.get(key) or []
        if isinstance(items, list):
            out[key] = _truncate_list(
                [_trim_highlights(i, max_chars=max_chars) if isinstance(i, dict) else i for i in items],
                limit,
            )
    if out.get("summary"):
        out["summary"] = _truncate_str(out["summary"], max_chars)
    return out


def compact_jd(jd: dict[str, Any] | None, max_requirements: int = 15, max_chars: int = 400) -> dict[str, Any]:
    """压缩 JD 分析结果。"""
    if not jd:
        return {}

    out = dict(jd)
    requirements = out.get("requirements") or []
    if isinstance(requirements, list):
        out["requirements"] = _truncate_list(requirements, max_requirements)
    if out.get("summary"):
        out["summary"] = _truncate_str(out["summary"], max_chars)
    return out


def compact_gap(gap: dict[str, Any] | None, max_gaps: int = 10, max_chars: int = 300) -> dict[str, Any]:
    """压缩差距分析结果。"""
    if not gap:
        return {}

    out = dict(gap)
    for key, limit in (("gaps", max_gaps), ("strengths", 8), ("recommendations", 8)):
        items = out.get(key) or []
        if isinstance(items, list):
            out[key] = _truncate_list(items, limit)
    return out


def compact_resume_content(
    content: dict[str, Any] | None, max_sections: int = 8, max_chars: int = 600
) -> dict[str, Any]:
    """压缩简历内容（评审/渲染用），限制板块数量与单板块长度。"""
    if not content:
        return {}

    out = dict(content)
    sections = out.get("sections") or []
    if isinstance(sections, list):
        trimmed = []
        for sec in sections[:max_sections]:
            if isinstance(sec, dict):
                sec = dict(sec)
                if sec.get("content"):
                    sec["content"] = _truncate_str(sec["content"], max_chars)
            trimmed.append(sec)
        out["sections"] = trimmed
    return out
