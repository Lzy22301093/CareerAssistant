"""简历模板框架 — 版式定义 + 结构化组装约束。

解决：模块顺序乱、自我评价过长、技能过简、空模块留白、导出排版松散。

三套模板（用户在生成步可选）：
- campus_one_page 校招一页纸（默认，密度最高）
- tech            技术岗（项目/技能优先，允许略密）
- general         通用（教育+经历+自评均衡）

数据仍兼容 ResumeContent {sections:[{title,content}]}，但正文按条目化约定生成：
- 基本信息：姓名行 + 联系方式行（导出层用作页眉）
- 经历：「名称 | 角色 | 时间」+ 若干「· 」bullet
- 技能：分组行「语言：…」等
- 自我评价：≤120 字，截断句号
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    label: str
    desc: str
    order: tuple[str, ...]
    max_summary_chars: int = 120
    max_bullets_per_exp: int = 3
    max_bullet_chars: int = 48
    max_experiences: int = 4
    hide_awards_on_one_page: bool = False
    summary_title: str = "个人优势"


TEMPLATES: dict[str, TemplateSpec] = {
    "campus_one_page": TemplateSpec(
        key="campus_one_page",
        label="校招一页纸",
        desc="应届首选：头信息+教育+项目/实习+技能+短自评，空模块隐藏",
        order=(
            "基本信息",
            "求职意向",
            "教育背景",
            "实习/工作经历",
            "项目经历",
            "技能",
            "个人优势",
            "证书/荣誉",
        ),
        max_summary_chars=100,
        max_bullets_per_exp=3,
        max_bullet_chars=44,
        max_experiences=3,
        hide_awards_on_one_page=True,
        summary_title="个人优势",
    ),
    "tech": TemplateSpec(
        key="tech",
        label="技术岗",
        desc="项目与技能前置，经历条目更细，适合开发/算法投递",
        order=(
            "基本信息",
            "求职意向",
            "项目经历",
            "实习/工作经历",
            "技能",
            "教育背景",
            "个人优势",
            "证书/荣誉",
        ),
        max_summary_chars=120,
        max_bullets_per_exp=4,
        max_bullet_chars=56,
        max_experiences=4,
        hide_awards_on_one_page=False,
        summary_title="个人优势",
    ),
    "general": TemplateSpec(
        key="general",
        label="通用版",
        desc="均衡结构，教育与经历并重，适合多种岗位",
        order=(
            "基本信息",
            "求职意向",
            "教育背景",
            "实习/工作经历",
            "项目经历",
            "个人优势",
            "技能",
            "证书/荣誉",
        ),
        max_summary_chars=150,
        max_bullets_per_exp=3,
        max_bullet_chars=52,
        max_experiences=4,
        hide_awards_on_one_page=False,
        summary_title="自我评价",
    ),
}

DEFAULT_TEMPLATE = "campus_one_page"


def get_template(key: str | None) -> TemplateSpec:
    k = (key or DEFAULT_TEMPLATE).strip()
    return TEMPLATES.get(k, TEMPLATES[DEFAULT_TEMPLATE])


def list_templates() -> list[dict[str, str]]:
    return [
        {"key": t.key, "label": t.label, "desc": t.desc}
        for t in (
            TEMPLATES["campus_one_page"],
            TEMPLATES["tech"],
            TEMPLATES["general"],
        )
    ]


def clamp_text(text: str, max_chars: int) -> str:
    """截断到 max_chars，尽量停在句读处。"""
    s = (text or "").strip()
    if max_chars <= 0 or len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    for p in ("。", "；", "！", "？", "，", "、", ". ", "; "):
        idx = cut.rfind(p)
        if idx >= max_chars // 2:
            return cut[: idx + len(p)].rstrip()
    return cut.rstrip() + "…"


def split_sentences(text: str) -> list[str]:
    s = (text or "").strip()
    if not s:
        return []
    parts = re.split(r"[。！？!?；;\n]+", s)
    return [p.strip() for p in parts if p.strip()]


def bullets_from_experience(
    *,
    duty: str,
    action: str,
    situation: str,
    task: str,
    result: str,
    achievement: str,
    max_bullets: int,
    max_chars: int,
) -> list[str]:
    """把经历字段压成 2~4 条「· 」bullet。"""
    candidates: list[str] = []
    for raw in (action, duty, task, situation):
        t = (raw or "").strip()
        if t and t not in candidates:
            candidates.append(t)
    outcome = (result or achievement or "").strip()
    bullets: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        for sent in split_sentences(c) or [c]:
            sent = clamp_text(sent, max_chars)
            if not sent or sent in seen:
                continue
            seen.add(sent)
            bullets.append(sent)
            if len(bullets) >= max_bullets - (1 if outcome else 0):
                break
        if len(bullets) >= max_bullets - (1 if outcome else 0):
            break
    if outcome:
        out = clamp_text(outcome, max_chars)
        if out and out not in seen:
            bullets.append(out)
    return bullets[:max_bullets]


def format_period(start: str | None, end: str | None, current: bool = False) -> str:
    """拼时间段展示：2022-09 / 2024-06 / current → 2022.09–至今。"""

    def norm(s: str) -> str:
        s = (s or "").strip()
        return s.replace("-", ".") if s else ""

    s = norm(start)
    e = "至今" if current else norm(end)
    if s and e:
        return f"{s}–{e}"
    return s or e


def _skill_label(item: Any) -> str:
    if isinstance(item, dict):
        name = str(item.get("name") or "").strip()
        level = str(item.get("level") or "").strip()
    elif hasattr(item, "name") or hasattr(item, "level"):
        name = str(getattr(item, "name", None) or "").strip()
        level = str(getattr(item, "level", None) or "").strip()
    else:
        return str(item or "").strip()
    if name and level:
        return f"{name}（{level}）"
    return name


def format_skills(skills: list[Any] | str | None) -> str:
    """技能分组：少则一行「、」；多则尝试按常见类别拆。支持 {name,level}。"""
    if not skills:
        return ""
    if isinstance(skills, str):
        items = [s.strip() for s in re.split(r"[、,，;；/|]", skills) if s.strip()]
    else:
        items = [_skill_label(s) for s in skills]
        items = [s for s in items if s]
    if not items:
        return ""
    if len(items) <= 6:
        return "、".join(items)
    groups: dict[str, list[str]] = {
        "语言": [],
        "框架": [],
        "数据/存储": [],
        "工具/平台": [],
        "其他": [],
    }
    lang_kw = ("python", "java", "c++", "golang", "go", "rust", "javascript", "typescript", "sql", "shell")
    fw_kw = ("spring", "django", "flask", "fastapi", "react", "vue", "pytorch", "tensorflow", "redis", "kafka")
    data_kw = ("mysql", "postgres", "mongo", "redis", "elasticsearch", "hadoop", "spark")
    tool_kw = ("docker", "k8s", "kubernetes", "git", "linux", "nginx", "jenkins", "aws", "阿里云")
    for it in items:
        low = it.lower()
        if any(k in low for k in lang_kw):
            groups["语言"].append(it)
        elif any(k in low for k in fw_kw):
            groups["框架"].append(it)
        elif any(k in low for k in data_kw):
            groups["数据/存储"].append(it)
        elif any(k in low for k in tool_kw):
            groups["工具/平台"].append(it)
        else:
            groups["其他"].append(it)
    lines = [f"{k}：{'、'.join(v)}" for k, v in groups.items() if v]
    return "\n".join(lines) if lines else "、".join(items)


def format_education_entry(entry: Any) -> str:
    """单条教育：结构化 dict/对象或纯文本 → 一行。"""
    if entry is None:
        return ""
    if isinstance(entry, str):
        return entry.strip()

    def get(key: str) -> str:
        if isinstance(entry, dict):
            v = entry.get(key)
        else:
            v = getattr(entry, key, None)
        if v is None:
            return ""
        if key == "current":
            return bool(v)
        return str(v).strip()

    if isinstance(entry, dict):
        current = bool(entry.get("current"))
    else:
        current = bool(getattr(entry, "current", False))

    school = get("school")
    degree = get("degree")
    major = get("major")
    period = format_period(get("start"), get("end"), current)
    gpa = get("gpa")
    rank = get("rank")
    courses = get("courses")

    parts = [p for p in (school, degree, major) if p]
    line = " · ".join(parts)
    if period:
        line = f"{line} · {period}" if line else period
    extras = []
    if gpa:
        extras.append(f"GPA {gpa}" if not gpa.upper().startswith("GPA") else gpa)
    if rank:
        extras.append(rank if "排名" in rank or "rank" in rank.lower() else f"排名 {rank}")
    if extras:
        line = f"{line}（{'；'.join(extras)}）" if line else "；".join(extras)
    if courses:
        line = f"{line}\n主修课程：{courses}" if line else f"主修课程：{courses}"
    return line


def format_education(edu: list | str | None) -> str:
    if not edu:
        return ""
    if isinstance(edu, str):
        return edu.strip()
    lines = []
    for e in edu:
        s = format_education_entry(e)
        if s:
            lines.append(s)
    return "\n".join(lines)


def format_self_eval(soft: dict[str, Any], spec: TemplateSpec) -> str:
    parts: list[str] = []
    for key in ("self_eval", "personality", "vision"):
        v = soft.get(key)
        s = (v or "").strip() if isinstance(v, str) else ""
        if s and s not in parts:
            parts.append(s)
    merged = " ".join(parts)
    # 压成一句/顿号风格短文
    merged = re.sub(r"\s+", " ", merged).strip()
    return clamp_text(merged, spec.max_summary_chars)


@dataclass
class AssembledResume:
    sections: list[dict[str, str]] = field(default_factory=list)
    template: str = DEFAULT_TEMPLATE

    def to_content(self) -> dict[str, Any]:
        raw = "\n\n".join(f"{s['title']}\n{s['content']}" for s in self.sections)
        return {"sections": self.sections, "raw_text": raw}


def _exp_header(exp: Any) -> str:
    company = str(getattr(exp, "company", None) or "").strip()
    title = str(getattr(exp, "title", None) or "").strip()
    duration = str(getattr(exp, "duration", None) or "").strip()
    if not duration:
        duration = format_period(
            getattr(exp, "start", None),
            getattr(exp, "end", None),
            bool(getattr(exp, "current", False)),
        )
    tech = str(getattr(exp, "tech_stack", None) or "").strip()
    bits = [b for b in (company, title, tech, duration) if b]
    return " | ".join(bits)


def _split_experiences(experiences: list[Any] | None) -> tuple[list[Any], list[Any]]:
    work: list[Any] = []
    projects: list[Any] = []
    for exp in experiences or []:
        exp_type = str(getattr(exp, "exp_type", "项目") or "项目")
        if exp_type in ("实习", "工作", "职场"):
            work.append(exp)
        else:
            projects.append(exp)
    return work, projects


def assemble_with_template(
    *,
    basic: dict[str, Any],
    directions: list[str],
    soft: dict[str, Any],
    experiences: list[Any] | None = None,
    internships: list[Any] | None = None,
    projects: list[Any] | None = None,
    educations: list[Any] | None = None,
    skills: list[Any] | None = None,
    template_key: str | None = None,
    page_preference: str = "one_page",
) -> AssembledResume:
    """按模板组装结构化简历（纯文本，无 Markdown）。

    优先使用 educations / internships / projects / skills；
    experiences 仅作旧版兼容，按 exp_type 分流。
    """
    spec = get_template(template_key)
    one_page = (page_preference or "one_page") == "one_page"

    # --- 基本信息（页眉数据源）---
    info_lines: list[str] = []
    name = str(basic.get("name") or "").strip()
    if name:
        info_lines.append(f"姓名：{name}")
    contact_bits: list[str] = []
    for key, label in (
        ("phone", "电话"),
        ("email", "邮箱"),
        ("location", "城市"),
        ("gender", "性别"),
        ("birthday", "出生日期"),
    ):
        v = basic.get(key)
        if v:
            contact_bits.append(f"{label}：{str(v).strip()}")
    if contact_bits:
        info_lines.append("联系方式：" + " · ".join(contact_bits))
    if info_lines:
        sections = [{"title": "基本信息", "content": "\n".join(info_lines)}]
    else:
        sections = []

    # --- 求职意向 ---
    dirs = [d.strip() for d in (directions or []) if d and str(d).strip()]
    if dirs:
        sections.append({"title": "求职意向", "content": "、".join(dirs[:3])})

    # --- 教育 ---
    edu_source = educations if educations else basic.get("education")
    edu_text = format_education(edu_source)
    if edu_text:
        sections.append({"title": "教育背景", "content": edu_text})

    # --- 实习 / 项目 ---
    work_list = list(internships or [])
    project_list = list(projects or [])
    if not work_list and not project_list and experiences:
        work_list, project_list = _split_experiences(experiences)

    max_exp = spec.max_experiences if one_page else spec.max_experiences + 1
    work_blocks: list[str] = []
    project_blocks: list[str] = []
    count = 0
    for bucket, is_work in ((work_list, True), (project_list, False)):
        for exp in bucket:
            if count >= max_exp:
                break
            header = _exp_header(exp)
            bullets = bullets_from_experience(
                duty=getattr(exp, "duty", None) or "",
                action=getattr(exp, "action", None) or "",
                situation=getattr(exp, "situation", None) or "",
                task=getattr(exp, "task", None) or "",
                result=getattr(exp, "result", None) or "",
                achievement=getattr(exp, "achievement", None) or "",
                max_bullets=spec.max_bullets_per_exp,
                max_chars=spec.max_bullet_chars,
            )
            if not header and not bullets:
                continue
            lines = [header] if header else []
            lines.extend(f"· {b}" for b in bullets)
            block = "\n".join(lines)
            if is_work:
                work_blocks.append(block)
            else:
                project_blocks.append(block)
            count += 1
        if count >= max_exp:
            break
    if work_blocks:
        sections.append({"title": "实习/工作经历", "content": "\n\n".join(work_blocks)})
    if project_blocks:
        sections.append({"title": "项目经历", "content": "\n\n".join(project_blocks)})

    # --- 技能 ---
    skill_source = skills if skills else (soft.get("skills") or basic.get("skills") or [])
    skill_text = format_skills(skill_source)
    if skill_text:
        sections.append({"title": "技能", "content": skill_text})

    # --- 自我评价 / 个人优势 ---
    summary = format_self_eval(soft, spec)
    if summary:
        sections.append({"title": spec.summary_title, "content": summary})

    # --- 证书 ---
    certs = basic.get("certifications")
    if certs and not (one_page and spec.hide_awards_on_one_page):
        cert_text = (
            "\n".join(str(c).strip() for c in certs if str(c).strip())
            if isinstance(certs, list)
            else str(certs).strip()
        )
        if cert_text:
            # 一页纸时最多 3 条
            if one_page:
                lines = [ln for ln in cert_text.splitlines() if ln.strip()][:3]
                cert_text = "\n".join(lines)
            if cert_text:
                sections.append({"title": "证书/荣誉", "content": cert_text})

    # --- 按模板顺序排序，未知标题靠后 ---
    order = list(spec.order)
    sections.sort(
        key=lambda s: (
            order.index(s["title"]) if s["title"] in order else len(order) + 1,
            s["title"],
        )
    )
    # 空模块已不生成；再滤一次
    sections = [s for s in sections if s.get("content", "").strip()]

    return AssembledResume(sections=sections, template=spec.key)
