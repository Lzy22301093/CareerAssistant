"""Profile Extractor Agent — 从简历文本提取候选人画像。"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.llm import Message, Role

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的简历解析助手。你的任务是从简历文本中提取候选人的结构化画像。

请以 JSON 格式返回，包含以下字段：
{
    "name": "候选人姓名",
    "email": "邮箱",
    "phone": "电话",
    "summary": "个人简介",
    "skills": ["技能1", "技能2"],
    "experience": [
        {
            "company": "公司名",
            "title": "职位",
            "duration": "2022-2024",
            "highlights": ["成就1", "成就2"]
        }
    ],
    "projects": [
        {
            "name": "项目名",
            "description": "项目描述",
            "tech_stack": ["技术1", "技术2"],
            "highlights": ["亮点1"]
        }
    ],
    "education": [
        {
            "school": "学校名",
            "degree": "学位",
            "major": "专业",
            "year": "毕业年份"
        }
    ],
    "certifications": ["证书1", "证书2"]
}

要求：
1. skills 至少提取 5 个
2. experience 按时间倒序排列
3. 只返回 JSON，不要添加额外说明
4. 如果简历文本中没有某个字段的信息，使用空数组或空字符串"""


class ProfileExtractorAgent(BaseAgent):
    """从简历文本提取候选人画像（name, skills, experience 等）。"""

    name = "profile_extractor"
    description = "从简历提取候选人画像"

    def build_messages(self, **kwargs) -> list[Message]:
        resume_text = kwargs.get("resume_text", "")

        # 记录传入的简历文本信息
        logger.info(f"[ProfileExtractor] 接收到简历文本: {len(resume_text)} 字符")
        if len(resume_text) < 100:
            logger.warning(f"[ProfileExtractor] 简历文本过短，可能影响解析质量: {resume_text[:200]}")

        # 限制文本长度，防止 token 溢出（约 4 字符 = 1 token，预留 2000 tokens 给 prompt）
        max_text_length = 12000  # 约 3000 tokens
        if len(resume_text) > max_text_length:
            logger.warning(f"[ProfileExtractor] 简历文本过长 ({len(resume_text)} 字符)，截断到 {max_text_length} 字符")
            resume_text = resume_text[:max_text_length] + "\n\n... (文本过长，已截断)"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=f"请解析以下简历：\n\n{resume_text}"),
        ]

    def parse_response(self, content: str) -> dict:
        logger.info(f"[ProfileExtractor] LLM 响应长度: {len(content)} 字符")
        logger.debug(f"[ProfileExtractor] LLM 响应内容:\n{content[:1000]}")

        result = self.extract_json(content)

        if result and ("name" in result or "skills" in result):
            # 验证关键字段
            name = result.get("name", "")
            skills = result.get("skills", [])
            experience = result.get("experience", [])
            education = result.get("education", [])

            logger.info(f"[ProfileExtractor] 解析成功: name={name}, skills={len(skills)}个, experience={len(experience)}段, education={len(education)}段")

            # 检查是否是明显编造的数据
            if not name and not skills and not experience and not education:
                logger.warning(f"[ProfileExtractor] 解析结果所有关键字段为空，可能是编造的数据")

            return result

        # JSON 解析失败，返回 fallback
        logger.warning(f"[ProfileExtractor] JSON 解析失败，返回原始内容作为 summary")
        logger.debug(f"[ProfileExtractor] 原始内容前 500 字符: {content[:500]}")

        return {
            "name": "",
            "email": "",
            "phone": "",
            "summary": content.strip()[:500],  # 限制长度
            "skills": [],
            "experience": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "_raw": content[:1000],  # 限制长度
            "_parse_error": True,
        }
