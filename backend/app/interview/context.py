"""面试上下文组装：JD + 简历为主，画像为补充。"""

from __future__ import annotations

import re
from typing import Any

# 单次喂给 LLM 的简历上限（字符），避免 prompt 过长
MAX_RESUME_CHARS = 3500
MAX_PROFILE_CHARS = 800


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", (text or "").strip())


def compact_resume(resume: dict[str, Any] | None) -> dict[str, Any]:
    """压缩简历为面试可用的紧凑结构。

    输入可为：{sections:[{title,content}], raw_text} 或含 document_id/title 等。
    """
    if not resume or not isinstance(resume, dict):
        return {}

    sections = resume.get("sections")
    raw = _clean(str(resume.get("raw_text") or ""))
    blocks: list[dict[str, str]] = []
    if isinstance(sections, list):
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            title = _clean(str(sec.get("title") or ""))
            content = _clean(str(sec.get("content") or ""))
            if title or content:
                blocks.append({"title": title, "content": content})
    if not blocks and raw:
        # 仅有 raw_text 时按空行切块
        parts = [p.strip() for p in re.split(r"\n{2,}", raw) if p.strip()]
        for p in parts[:12]:
            first, _, rest = p.partition("\n")
            blocks.append({"title": first[:40], "content": rest or first})

    # 截断总长
    used = 0
    kept: list[dict[str, str]] = []
    for b in blocks:
        piece = len(b["title"]) + len(b["content"]) + 2
        if used + piece > MAX_RESUME_CHARS:
            remain = MAX_RESUME_CHARS - used
            if remain > 80:
                b = {
                    "title": b["title"],
                    "content": b["content"][: max(0, remain - 20)] + "…",
                }
                kept.append(b)
            break
        kept.append(b)
        used += piece

    if not kept:
        return {}

    return {
        "document_id": resume.get("document_id"),
        "version_id": resume.get("version_id"),
        "title": _clean(str(resume.get("title") or ""))[:80],
        "sections": kept,
        "raw_text": "\n\n".join(
            (f"{b['title']}\n" if b["title"] else "") + b["content"] for b in kept
        )[:MAX_RESUME_CHARS],
    }


def compact_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    """画像只作补充：压缩为简短要点。"""
    if not profile or not isinstance(profile, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("name", "summary", "skills", "target_roles", "education"):
        v = profile.get(key)
        if not v:
            continue
        if isinstance(v, list):
            items = []
            for x in v[:8]:
                if isinstance(x, dict):
                    items.append(f"{x.get('title', '')}: {x.get('content', '')}".strip(": "))
                else:
                    items.append(str(x)[:80])
            out[key] = items
        else:
            out[key] = str(v)[:200]
    return out


def format_resume_for_prompt(resume: dict[str, Any] | None) -> str:
    r = compact_resume(resume)
    if not r:
        return ""
    lines = [f"简历标题：{r.get('title') or '候选人简历'}"]
    for sec in r.get("sections") or []:
        if sec.get("title"):
            lines.append(f"### {sec['title']}")
        if sec.get("content"):
            lines.append(sec["content"])
    return "\n".join(lines)[:MAX_RESUME_CHARS]


def format_profile_supplement(profile: dict[str, Any] | None) -> str:
    p = compact_profile(profile)
    if not p:
        return ""
    bits = []
    if p.get("name"):
        bits.append(f"姓名：{p['name']}")
    if p.get("skills"):
        skills = p["skills"]
        bits.append("技能补充：" + ("、".join(skills) if isinstance(skills, list) else str(skills)))
    if p.get("target_roles"):
        bits.append("目标方向：" + "、".join(str(x) for x in p["target_roles"]))
    if p.get("summary"):
        bits.append(f"其他：{str(p['summary'])[:120]}")
    return "\n".join(bits)[:MAX_PROFILE_CHARS]


def extract_resume_topics(resume: dict[str, Any] | None) -> list[str]:
    """从简历标题/首行抽取可考察话题，补 JD topics。"""
    r = compact_resume(resume)
    topics: list[str] = []
    for sec in r.get("sections") or []:
        title = sec.get("title") or ""
        if any(k in title for k in ("项目", "实习", "工作", "经历")):
            for line in (sec.get("content") or "").splitlines():
                line = line.strip()
                if not line or line.startswith("·"):
                    continue
                # 取「名称 | 角色 | 时间」首段
                name = line.split("|")[0].strip()
                if 2 <= len(name) <= 40:
                    topics.append(name)
        if len(topics) >= 8:
            break
    return topics[:8]
