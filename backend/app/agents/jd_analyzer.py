"""JD Analyzer Agent — 分析职位描述，提取结构化信息。"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.llm import Message, Role

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的职位描述（JD）分析助手。你的任务是从 JD 文本中提取结构化信息。

请以 JSON 格式返回分析结果，包含以下字段：
{
    "job_title": "职位名称",
    "company": "公司名称",
    "location": "工作地点",
    "salary_range": "薪资范围（如有）",
    "summary": "职位概述（1-2句话）",
    "requirements": [
        {"category": "skill|experience|education|other", "content": "具体要求", "importance": "high|medium|low"}
    ],
    "nice_to_have": ["加分项1", "加分项2"],
    "keywords": ["关键词1", "关键词2"]
}

要求：
1. requirements 至少提取 3 个，最多 15 个
2. keywords 至少 5 个，用于后续匹配
3. 只返回 JSON，不要添加额外说明"""


class JDAnalyzerAgent(BaseAgent):
    """分析职位描述，提取 job_title、skills、requirements 等结构化数据。"""

    name = "jd_analyzer"
    description = "分析职位描述，提取结构化信息"

    # 提取类 Agent：低温度保证稳定，输出较小
    temperature = 0.2
    max_tokens = 2048

    def build_messages(self, **kwargs) -> list[Message]:
        jd_text = kwargs.get("jd_text", "")

        # 记录传入的 JD 文本信息
        logger.info(f"[JDAnalyzer] 接收到 JD 文本: {len(jd_text)} 字符")
        if len(jd_text) < 100:
            logger.warning(f"[JDAnalyzer] JD 文本过短，可能影响解析质量: {jd_text[:200]}")

        # 限制文本长度，防止 token 溢出
        max_text_length = 8000  # 约 2000 tokens
        if len(jd_text) > max_text_length:
            logger.warning(f"[JDAnalyzer] JD 文本过长 ({len(jd_text)} 字符)，截断到 {max_text_length} 字符")
            jd_text = jd_text[:max_text_length] + "\n\n... (文本过长，已截断)"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=f"请分析以下职位描述：\n\n{jd_text}"),
        ]

    def parse_response(self, content: str) -> dict:
        logger.info(f"[JDAnalyzer] LLM 响应长度: {len(content)} 字符")

        result = self.extract_json(content)

        if result and "job_title" in result:
            job_title = result.get("job_title", "")
            company = result.get("company", "")
            requirements = result.get("requirements", [])
            logger.info(f"[JDAnalyzer] 解析成功: job_title={job_title}, company={company}, requirements={len(requirements)}个")
            return result

        # JSON 解析失败，返回 fallback
        logger.warning(f"[JDAnalyzer] JSON 解析失败，返回原始内容作为 summary")
        return {
            "job_title": "",
            "company": "",
            "summary": content.strip()[:500],  # 限制长度
            "requirements": [],
            "nice_to_have": [],
            "keywords": [],
            "_raw": content[:1000],  # 限制长度
            "_parse_error": True,
        }
