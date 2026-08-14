"""信息提取工具：entity_extractor, keyword_extractor。"""

from __future__ import annotations

import json
from typing import Any

from .base import Tool, ToolResult


class EntityExtractorTool(Tool):
    """实体提取工具 — 使用 LLM 从文本中提取结构化信息。"""

    name = "entity_extractor"
    description = "从文本中提取实体信息（姓名、公司、技能、职位等）。"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待提取的文本",
            },
            "entity_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要提取的实体类型列表，如 ['name', 'company', 'skill']",
            },
        },
        "required": ["text"],
    }

    # 默认实体类型
    _DEFAULT_TYPES = ["name", "company", "title", "skill", "education", "location"]

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    async def execute(
        self,
        text: str,
        entity_types: list[str] | None = None,
        **kwargs,
    ) -> ToolResult:
        """提取实体。"""
        if not self._llm:
            return ToolResult.fail("LLM provider 未初始化")

        try:
            types = entity_types or self._DEFAULT_TYPES
            result = await self._extract(text, types)
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(f"实体提取失败: {e}")

    async def _extract(self, text: str, entity_types: list[str]) -> dict:
        """调用 LLM 提取实体。"""
        prompt = f"""请从以下文本中提取实体信息。

待提取的实体类型：{', '.join(entity_types)}

文本内容：
{text[:3000]}  # 限制长度，避免 token 超限

请返回 JSON 格式，包含以下字段：
{{
    "entities": {{
        "name": "姓名",
        "company": "公司名称",
        "title": "职位",
        "skills": ["技能1", "技能2"],
        "education": "学历",
        "location": "所在地"
    }}
}}

注意：
1. 只提取文本中明确提到的信息
2. 未提及的字段设为 null
3. skills 是数组，包含所有提到的技能
4. 返回且仅返回 JSON 对象，不要有其他内容"""

        response = await self._llm.generate(prompt)
        return self._parse_response(response)

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 响应。"""
        # 尝试提取 JSON
        try:
            # 移除可能的 markdown 代码块标记
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试找到 JSON 部分
            import re
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group())
            raise ValueError(f"无法解析 LLM 响应: {response[:200]}")


class KeywordExtractorTool(Tool):
    """关键词提取工具 — 使用 LLM 从文本中提取关键词。"""

    name = "keyword_extractor"
    description = "从文本中提取关键词和短语。"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待提取的文本",
            },
            "max_keywords": {
                "type": "integer",
                "description": "最大关键词数量",
            },
            "context": {
                "type": "string",
                "description": "上下文说明（如 'job_description' 或 'resume'）",
            },
        },
        "required": ["text"],
    }

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    async def execute(
        self,
        text: str,
        max_keywords: int = 20,
        context: str = "",
        **kwargs,
    ) -> ToolResult:
        """提取关键词。"""
        if not self._llm:
            return ToolResult.fail("LLM provider 未初始化")

        try:
            result = await self._extract(text, max_keywords, context)
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(f"关键词提取失败: {e}")

    async def _extract(
        self, text: str, max_keywords: int, context: str
    ) -> dict:
        """调用 LLM 提取关键词。"""
        context_hint = ""
        if context == "job_description":
            context_hint = "这是一份职位描述（JD），请提取：技术栈、任职要求、职责描述等关键信息。"
        elif context == "resume":
            context_hint = "这是一份简历，请提取：技能、项目经验、工作经历等关键信息。"

        prompt = f"""请从以下文本中提取关键词和短语。

{context_hint}

文本内容：
{text[:3000]}

要求：
1. 最多提取 {max_keywords} 个关键词
2. 按重要性排序
3. 包含：技术术语、行业术语、关键技能、重要概念等
4. 返回 JSON 格式

返回格式：
{{
    "keywords": [
        {{"keyword": "关键词1", "relevance": 0.95, "category": "skill"}},
        {{"keyword": "关键词2", "relevance": 0.85, "category": "technology"}}
    ],
    "summary": "文本摘要（1-2句话）"
}}

category 可选值：skill, technology, concept, role, industry, other
返回且仅返回 JSON 对象，不要有其他内容。"""

        response = await self._llm.generate(prompt)
        return self._parse_response(response)

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 响应。"""
        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group())
            raise ValueError(f"无法解析 LLM 响应: {response[:200]}")
