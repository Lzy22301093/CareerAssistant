"""简历处理服务 — 负责简历解析、内容生成和渲染。"""

from __future__ import annotations

import json
from typing import Any

from app.llm.base import LLMProvider, Message, Role
from app.models.schemas import (
    GapAnalysis,
    GapItem,
    Profile,
    ResumeContent,
    ResumeSection,
    RenderConfig,
)
from app.tools.file_tools import FileParserTool
from app.tools.extract_tools import EntityExtractorTool
from app.tools.render_tools import HtmlRendererTool, TemplateSearchTool


class ResumeService:
    """简历处理服务。

    职责：
    - 解析简历文件，提取候选人画像
    - 生成简历内容（基于 JD + Profile）
    - 差距分析（JD vs Profile）
    - 渲染 HTML 简历
    """

    def __init__(self, llm: LLMProvider):
        self._llm = llm
        self._file_parser = FileParserTool()
        self._entity_extractor = EntityExtractorTool(llm_provider=llm)
        self._html_renderer = HtmlRendererTool()
        self._template_search = TemplateSearchTool()

    # ---- 简历解析 ----

    async def parse_resume_file(self, file_path: str) -> str:
        """解析简历文件，返回纯文本。"""
        result = await self._file_parser.execute(file_path=file_path)
        if not result.success:
            raise ValueError(f"文件解析失败: {result.error}")
        return result.data["text"]

    async def extract_profile(self, resume_text: str, existing: dict | None = None) -> Profile:
        """从简历文本中提取候选人画像。"""
        context = ""
        if existing:
            context = f"\n已有信息（请补充和更新）：\n{json.dumps(existing, ensure_ascii=False, indent=2)}"

        prompt = f"""请从以下简历文本中提取候选人信息。

{context}

简历内容：
{resume_text[:4000]}

请返回 JSON 格式：
{{
    "name": "姓名",
    "email": "邮箱",
    "phone": "电话",
    "education": [
        {{"school": "学校", "degree": "学位", "major": "专业", "period": "2018-2022"}}
    ],
    "experience": [
        {{
            "company": "公司名",
            "title": "职位",
            "duration": "2022-2024",
            "highlights": ["成就1", "成就2"]
        }}
    ],
    "projects": [
        {{
            "name": "项目名",
            "description": "项目描述",
            "tech_stack": ["Python", "FastAPI"],
            "highlights": ["亮点1"]
        }}
    ],
    "skills": ["Python", "FastAPI", "MySQL"],
    "certifications": ["证书1"],
    "summary": "个人简介"
}}

返回且仅返回 JSON 对象。"""

        messages = [Message(role=Role.USER, content=prompt)]
        response = await self._llm.chat(messages, temperature=0.3)

        try:
            data = self._parse_json(response.content)
            return Profile(**data)
        except Exception as e:
            return Profile(summary=f"解析失败: {e}")

    # ---- 差距分析 ----

    async def analyze_gap(self, jd_analysis: dict, profile: dict) -> GapAnalysis:
        """分析 JD 和 Profile 的差距。"""
        prompt = f"""请分析候选人画像与职位要求之间的差距。

职位分析：
{json.dumps(jd_analysis, ensure_ascii=False, indent=2)[:2000]}

候选人画像：
{json.dumps(profile, ensure_ascii=False, indent=2)[:2000]}

请返回 JSON 格式：
{{
    "overall_score": 75.5,
    "gaps": [
        {{
            "category": "skill",
            "requirement": "Docker容器化",
            "current_level": "了解基础概念",
            "gap_severity": "major",
            "suggestion": "建议学习 Docker 基础操作和 Docker Compose"
        }}
    ],
    "strengths": ["Python经验丰富", "有团队管理经验"],
    "recommendations": ["补充Docker经验", "量化项目成果"]
}}

overall_score: 0-100 的匹配度分数
gap_severity: critical（关键缺失）, major（较大差距）, minor（小差距）
category: skill, experience, education, soft_skill

返回且仅返回 JSON 对象。"""

        messages = [Message(role=Role.USER, content=prompt)]
        response = await self._llm.chat(messages, temperature=0.3)

        try:
            data = self._parse_json(response.content)
            return GapAnalysis(
                overall_score=data.get("overall_score", 0),
                gaps=[GapItem(**g) for g in data.get("gaps", [])],
                strengths=data.get("strengths", []),
                recommendations=data.get("recommendations", []),
            )
        except Exception as e:
            return GapAnalysis(
                overall_score=0,
                recommendations=[f"分析失败: {e}"],
            )

    # ---- 简历内容生成 ----

    async def generate_content(
        self,
        jd_analysis: dict,
        profile: dict,
        gap_analysis: dict | None = None,
        user_instructions: str = "",
    ) -> ResumeContent:
        """生成简历内容。"""
        gap_context = ""
        if gap_analysis:
            gap_context = f"\n差距分析：\n{json.dumps(gap_analysis, ensure_ascii=False, indent=2)[:1500]}"

        instruction_context = ""
        if user_instructions:
            instruction_context = f"\n用户要求：{user_instructions}"

        prompt = f"""请根据以下信息生成一份专业的简历内容。

职位分析：
{json.dumps(jd_analysis, ensure_ascii=False, indent=2)[:1500]}

候选人画像：
{json.dumps(profile, ensure_ascii=False, indent=2)[:1500]}
{gap_context}
{instruction_context}

请返回 JSON 格式：
{{
    "sections": [
        {{
            "title": "个人简介",
            "content": "5年Python开发经验..."
        }},
        {{
            "title": "专业技能",
            "content": "- Python / FastAPI / Django\\n- MySQL / Redis / MongoDB"
        }},
        {{
            "title": "工作经历",
            "content": "### 字节跳动 | 高级后端工程师 | 2020-至今\\n- 负责核心服务开发..."
        }},
        {{
            "title": "项目经历",
            "content": "### 分布式任务调度系统\\n- 使用 Python + Redis 实现..."
        }},
        {{
            "title": "教育背景",
            "content": "北京大学 | 计算机科学与技术 | 硕士 | 2018-2021"
        }}
    ],
    "raw_text": "完整的简历纯文本"
}}

要求：
1. 针对 JD 定制，突出匹配的技能和经验
2. 使用量化指标（如：性能提升30%）
3. 内容简洁专业
4. 确保覆盖所有重要信息

返回且仅返回 JSON 对象。"""

        messages = [Message(role=Role.USER, content=prompt)]
        response = await self._llm.chat(messages, temperature=0.5)

        try:
            data = self._parse_json(response.content)
            return ResumeContent(
                sections=[ResumeSection(**s) for s in data.get("sections", [])],
                raw_text=data.get("raw_text", ""),
            )
        except Exception as e:
            return ResumeContent(
                sections=[ResumeSection(title="错误", content=f"生成失败: {e}")],
            )

    # ---- HTML 渲染 ----

    async def render_html(
        self,
        content: dict,
        template: str = "modern",
        config: RenderConfig | None = None,
    ) -> str:
        """渲染 HTML 简历。"""
        # 准备渲染数据
        render_data = self._prepare_render_data(content, config)

        result = await self._html_renderer.execute(
            template_name=template, data=render_data
        )
        if not result.success:
            raise ValueError(f"渲染失败: {result.error}")

        return result.data["html"]

    async def list_templates(self) -> list[dict[str, Any]]:
        """列出可用模板。"""
        result = await self._template_search.execute(style="all")
        if not result.success:
            return []
        return result.data.get("templates", [])

    def _prepare_render_data(self, content: dict, config: RenderConfig | None) -> dict:
        """准备渲染数据。"""
        sections = content.get("sections", [])
        profile = content.get("profile", {})

        # 提取技能列表
        skills = []
        for section in sections:
            if "技能" in section.get("title", ""):
                # 从内容中提取技能
                lines = section.get("content", "").split("\n")
                for line in lines:
                    line = line.strip().lstrip("- •")
                    if line:
                        skills.append(line)

        return {
            "name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "location": profile.get("location", ""),
            "title": profile.get("title", ""),
            "summary": profile.get("summary", ""),
            "skills": skills[:10],
            "sections": sections,
            "experience": profile.get("experience", []),
            "education": profile.get("education", []),
        }

    # ---- 完整流程 ----

    async def process_resume(
        self,
        resume_text: str | None = None,
        file_path: str | None = None,
        jd_analysis: dict | None = None,
        existing_profile: dict | None = None,
        user_instructions: str = "",
        template: str = "modern",
    ) -> dict[str, Any]:
        """完整的简历处理流程。

        Returns:
            包含 profile, gap_analysis, content, html 的字典
        """
        # 1. 获取简历文本
        if file_path:
            text = await self.parse_resume_file(file_path)
        elif resume_text:
            text = resume_text
        else:
            raise ValueError("必须提供 resume_text 或 file_path")

        # 2. 提取画像
        profile = await self.extract_profile(text, existing_profile)

        # 3. 差距分析（如果有 JD）
        gap_analysis = None
        if jd_analysis:
            gap_analysis = await self.analyze_gap(jd_analysis, profile.model_dump())

        # 4. 生成内容
        content = await self.generate_content(
            jd_analysis=jd_analysis or {},
            profile=profile.model_dump(),
            gap_analysis=gap_analysis.model_dump() if gap_analysis else None,
            user_instructions=user_instructions,
        )

        # 5. 渲染 HTML
        html = await self.render_html(content.model_dump(), template)

        return {
            "profile": profile.model_dump(),
            "gap_analysis": gap_analysis.model_dump() if gap_analysis else None,
            "content": content.model_dump(),
            "html": html,
        }

    def _parse_json(self, text: str) -> dict:
        """解析 LLM 返回的 JSON。"""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                return json.loads(match.group())
            raise ValueError(f"无法解析 JSON: {text[:200]}")
