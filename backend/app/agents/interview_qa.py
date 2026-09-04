"""Interview Q&A Agent — 根据 JD 和画像生成面试题。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个专业的面试辅导助手。根据职位要求（Job）和候选人画像（Profile），生成有针对性的面试题。

## 输出要求
- 只返回一个合法 JSON 对象，不要 Markdown 代码块、注释或任何解释文字
- 所有 key 使用双引号，字符串中的双引号用 \\" 转义
- 即使信息不足，也要返回合法 JSON（可用题目数量少一些）

## JSON 格式
{
    "questions": [
        {
            "question": "面试问题",
            "category": "technical|project_deep_dive|behavioral",
            "difficulty": "easy|medium|hard",
            "answer_points": ["要点1", "要点2", "要点3"],
            "sample_answer": "基于候选人材料的参考答案（100-200字）"
        }
    ]
}

## 题目要求
1. 生成 6-10 道面试题，覆盖三类：
   - technical：技术知识题（语言、框架、算法、系统设计等）
   - project_deep_dive：深挖候选人项目/实习经历（追问细节、权衡决策、量化成果）
   -behavioral：行为/情景题（团队协作、冲突处理、压力管理）
2. 难度分布：2 easy, 3-4 medium, 2-3 hard
3. answer_points 列出 3-5 个回答关键点
4. sample_answer 必须**基于候选人实际材料**，不要泛泛而谈
5. 如果有差距分析（gap），重点针对薄弱环节出题"""


class InterviewQAAgent(BaseAgent):
    """根据 JD、画像和差距分析生成面试题。"""

    name = "interview_qa"
    description = "生成针对性面试题"
    max_parse_attempts = 2
    json_mode = True

    def build_messages(self, **kwargs) -> list[Message]:
        from app.tools.context import compact_gap, compact_jd, compact_profile

        jd_analysis = compact_jd(kwargs.get("jd_analysis", {}))
        profile = compact_profile(kwargs.get("profile", {}))
        gap_analysis = compact_gap(kwargs.get("gap_analysis", {}))
        user_instructions = kwargs.get("user_instructions", "")

        user_content = (
            f"## 职位要求 (Job)\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"## 候选人画像 (Profile)\n{json.dumps(profile, ensure_ascii=False, indent=2)}"
        )
        if gap_analysis:
            user_content += f"\n\n## 差距分析 (Gap)\n{json.dumps(gap_analysis, ensure_ascii=False, indent=2)}"
        if user_instructions:
            user_content += f"\n\n## 用户特别要求\n{user_instructions}"
        user_content += "\n\n请根据以上信息生成面试题。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "questions" in result:
            # 校验 questions 是列表且非空
            questions = result["questions"]
            if isinstance(questions, list) and len(questions) > 0:
                return result
        return {
            "questions": [],
            "_raw": content,
            "_parse_error": True,
        }
