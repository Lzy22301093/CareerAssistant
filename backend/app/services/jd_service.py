"""JD 处理服务 — 负责 JD 解析和分析。"""

from __future__ import annotations

import json
from typing import Any

from app.llm.base import LLMProvider, Message, Role
from app.models.schemas import JDAnalysis, JDRequirement
from app.tools.file_tools import FileParserTool, TextCleanerTool
from app.tools.extract_tools import KeywordExtractorTool


class JDService:
    """JD 处理服务。

    职责：
    - 解析 JD 文件（PDF/DOCX/TXT）
    - 分析 JD 内容，提取结构化信息
    - 提取关键词
    """

    def __init__(self, llm: LLMProvider):
        self._llm = llm
        self._file_parser = FileParserTool()
        self._text_cleaner = TextCleanerTool()
        self._keyword_extractor = KeywordExtractorTool(llm_provider=llm)

    async def parse_file(self, file_path: str) -> str:
        """解析 JD 文件，返回纯文本。"""
        result = await self._file_parser.execute(file_path=file_path)
        if not result.success:
            raise ValueError(f"文件解析失败: {result.error}")

        # 清洗文本
        cleaned = await self._text_cleaner.execute(
            text=result.data["text"], mode="basic"
        )
        return cleaned.data["text"] if cleaned.success else result.data["text"]

    async def analyze(self, jd_text: str) -> JDAnalysis:
        """分析 JD 文本，返回结构化结果。"""
        prompt = f"""请分析以下职位描述（JD），提取结构化信息。

JD 内容：
{jd_text[:4000]}

请返回 JSON 格式：
{{
    "job_title": "职位名称",
    "company": "公司名称",
    "requirements": [
        {{"category": "skill", "content": "Python 3.10+", "importance": "high"}},
        {{"category": "experience", "content": "3年以上开发经验", "importance": "high"}},
        {{"category": "education", "content": "本科及以上", "importance": "medium"}}
    ],
    "nice_to_have": ["Docker经验", "开源项目贡献"],
    "salary_range": "20-30K",
    "location": "北京",
    "summary": "职位简要描述"
}}

category 可选值：skill, experience, education, soft_skill, other
importance 可选值：high, medium, low
返回且仅返回 JSON 对象。"""

        messages = [Message(role=Role.USER, content=prompt)]
        response = await self._llm.chat(messages, temperature=0.3)

        try:
            data = self._parse_json(response.content)
            return JDAnalysis(
                job_title=data.get("job_title", ""),
                company=data.get("company", ""),
                requirements=[
                    JDRequirement(**r) for r in data.get("requirements", [])
                ],
                nice_to_have=data.get("nice_to_have", []),
                salary_range=data.get("salary_range"),
                location=data.get("location"),
                summary=data.get("summary", ""),
            )
        except Exception as e:
            # 解析失败时返回基础结构
            return JDAnalysis(
                job_title="未知职位",
                summary=f"JD 解析失败: {e}",
            )

    async def extract_keywords(self, jd_text: str) -> list[dict[str, Any]]:
        """从 JD 中提取关键词。"""
        result = await self._keyword_extractor.execute(
            text=jd_text, context="job_description", max_keywords=15
        )
        if not result.success:
            return []
        return result.data.get("keywords", [])

    async def process(self, jd_text: str | None = None, file_path: str | None = None) -> dict[str, Any]:
        """完整的 JD 处理流程。

        Args:
            jd_text: JD 文本内容（与 file_path 二选一）
            file_path: JD 文件路径

        Returns:
            包含 analysis 和 keywords 的字典
        """
        # 获取文本
        if file_path:
            text = await self.parse_file(file_path)
        elif jd_text:
            text = jd_text
        else:
            raise ValueError("必须提供 jd_text 或 file_path")

        # 并行分析和提取关键词
        analysis = await self.analyze(text)
        keywords = await self.extract_keywords(text)

        return {
            "jd_text": text,
            "analysis": analysis.model_dump(),
            "keywords": keywords,
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
