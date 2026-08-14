"""知识检索工具：question_bank, industry_standards。"""

from __future__ import annotations

from typing import Any

from .base import Tool, ToolResult


class QuestionBankTool(Tool):
    """面试题库工具 — 搜索和生成面试题。"""

    name = "question_bank"
    description = "搜索面试题库，获取常见面试题和参考答案。"
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["technical", "behavioral", "situational", "all"],
                "description": "题目类别",
            },
            "topic": {
                "type": "string",
                "description": "具体主题（如 'Python', '系统设计', '团队协作'）",
            },
            "difficulty": {
                "type": "string",
                "enum": ["easy", "medium", "hard", "all"],
                "description": "难度级别",
            },
            "count": {
                "type": "integer",
                "description": "返回题目数量",
            },
        },
        "required": [],
    }

    # 预定义题库
    _QUESTIONS = [
        # 技术题
        {
            "id": "tech_001",
            "category": "technical",
            "topic": "Python",
            "difficulty": "medium",
            "question": "请解释 Python 中的装饰器（Decorator）是什么，并举例说明其用途。",
            "key_points": ["函数作为参数", "闭包", "语法糖", "常见应用场景"],
            "sample_answer": "装饰器是一种设计模式，它允许在不修改原函数代码的情况下，为函数添加额外的功能。在 Python 中，装饰器本质上是一个接收函数作为参数的高阶函数，返回一个新的函数。",
        },
        {
            "id": "tech_002",
            "category": "technical",
            "topic": "Python",
            "difficulty": "hard",
            "question": "请解释 Python 的 GIL（全局解释器锁）是什么，它如何影响多线程程序的性能？",
            "key_points": ["GIL 定义", "多线程限制", "多进程替代", "异步编程"],
            "sample_answer": "GIL 是 CPython 解释器中的一个互斥锁，它确保同一时刻只有一个线程执行 Python 字节码。这意味着在 CPU 密集型任务中，多线程无法利用多核优势。",
        },
        {
            "id": "tech_003",
            "category": "technical",
            "topic": "数据库",
            "difficulty": "medium",
            "question": "请解释数据库索引是什么，以及何时应该使用索引。",
            "key_points": ["索引定义", "B-Tree 结构", "查询优化", "索引代价"],
            "sample_answer": "数据库索引是一种数据结构，用于快速查找表中的数据。类似于书籍的目录，索引可以显著加快查询速度，但会增加写入开销和存储空间。",
        },
        # 行为题
        {
            "id": "beh_001",
            "category": "behavioral",
            "topic": "团队协作",
            "difficulty": "medium",
            "question": "请描述一次你在团队中解决冲突的经历。",
            "key_points": ["冲突背景", "解决过程", "沟通技巧", "最终结果"],
            "sample_answer": "使用 STAR 法则回答：情境（Situation）→ 任务（Task）→ 行动（Action）→ 结果（Result）。",
        },
        {
            "id": "beh_002",
            "category": "behavioral",
            "topic": "压力管理",
            "difficulty": "medium",
            "question": "请描述一次你在高压环境下工作的经历。",
            "key_points": ["压力来源", "应对策略", "时间管理", "成果"],
            "sample_answer": "描述具体的压力场景，说明你如何分解任务、优先排序、寻求支持，以及最终如何按时完成任务。",
        },
        # 情境题
        {
            "id": "sit_001",
            "category": "situational",
            "topic": "技术决策",
            "difficulty": "hard",
            "question": "如果你发现团队选择的技术方案有严重缺陷，但项目已经进行了一半，你会怎么做？",
            "key_points": ["问题分析", "沟通策略", "风险评估", "解决方案"],
            "sample_answer": "首先，我会收集充分的证据来支持我的观点。然后，我会与技术负责人私下沟通，提出我的担忧和替代方案。如果问题确实严重，我会建议召开技术评审会议。",
        },
    ]

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    async def execute(
        self,
        category: str = "all",
        topic: str = "",
        difficulty: str = "all",
        count: int = 5,
        **kwargs,
    ) -> ToolResult:
        """搜索面试题。"""
        try:
            # 筛选题目
            filtered = self._QUESTIONS

            if category != "all":
                filtered = [q for q in filtered if q["category"] == category]

            if topic:
                filtered = [
                    q for q in filtered
                    if topic.lower() in q["topic"].lower()
                    or topic.lower() in q["question"].lower()
                ]

            if difficulty != "all":
                filtered = [q for q in filtered if q["difficulty"] == difficulty]

            # 限制数量
            questions = filtered[:count]

            # 如果有 LLM，可以生成额外题目
            if self._llm and len(questions) < count:
                extra = await self._generate_questions(
                    category, topic, difficulty, count - len(questions)
                )
                questions.extend(extra)

            return ToolResult.ok(
                {"questions": questions, "total": len(questions)}
            )
        except Exception as e:
            return ToolResult.fail(f"面试题搜索失败: {e}")

    async def _generate_questions(
        self,
        category: str,
        topic: str,
        difficulty: str,
        count: int,
    ) -> list[dict]:
        """使用 LLM 生成额外题目。"""
        prompt = f"""请生成 {count} 道面试题。

要求：
- 类别：{category}
- 主题：{topic or '通用'}
- 难度：{difficulty}

返回 JSON 格式：
{{
    "questions": [
        {{
            "category": "{category}",
            "topic": "主题",
            "difficulty": "{difficulty}",
            "question": "题目内容",
            "key_points": ["要点1", "要点2"],
            "sample_answer": "参考答案"
        }}
    ]
}}

返回且仅返回 JSON 对象。"""

        response = await self._llm.generate(prompt)
        import json

        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
            return result.get("questions", [])
        except Exception:
            return []


class IndustryStandardsTool(Tool):
    """行业标准工具 — 查询行业标准和最佳实践。"""

    name = "industry_standards"
    description = "查询行业标准、最佳实践和参考案例。"
    parameters = {
        "type": "object",
        "properties": {
            "industry": {
                "type": "string",
                "description": "行业（如 'tech', 'finance', 'healthcare'）",
            },
            "topic": {
                "type": "string",
                "description": "具体主题（如 '简历格式', '技能要求', '面试流程'）",
            },
        },
        "required": ["topic"],
    }

    # 预定义行业标准
    _STANDARDS = {
        "tech": {
            "简历格式": {
                "title": "科技行业简历格式标准",
                "recommendations": [
                    "简洁明了，突出技术栈和项目经验",
                    "使用量化指标（如：性能提升 30%）",
                    "按时间倒序排列工作经历",
                    "包含 GitHub 或个人项目链接",
                ],
                "common_mistakes": [
                    "过于冗长（超过 2 页）",
                    "缺乏具体数据支撑",
                    "技术栈描述过于笼统",
                ],
            },
            "技能要求": {
                "title": "科技行业技能要求",
                "must_have": ["编程语言", "版本控制（Git）", "基本算法和数据结构"],
                "nice_to_have": ["云服务（AWS/GCP/Azure）", "容器化（Docker/K8s）", "CI/CD"],
                "soft_skills": ["沟通能力", "团队协作", "问题解决能力"],
            },
        },
        "finance": {
            "简历格式": {
                "title": "金融行业简历格式标准",
                "recommendations": [
                    "正式、专业的格式",
                    "强调证书和资质（CFA, CPA 等）",
                    "突出量化分析能力",
                    "包含教育背景和 GPA（如果优秀）",
                ],
            },
        },
    }

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    async def execute(
        self, topic: str, industry: str = "tech", **kwargs
    ) -> ToolResult:
        """查询行业标准。"""
        try:
            # 先从预定义数据中查找
            if industry in self._STANDARDS:
                industry_data = self._STANDARDS[industry]
                if topic in industry_data:
                    return ToolResult.ok(industry_data[topic])

            # 如果有 LLM，生成相关内容
            if self._llm:
                result = await self._generate_standards(industry, topic)
                return ToolResult.ok(result)

            # 返回默认建议
            return ToolResult.ok(
                {
                    "title": f"{industry} 行业 - {topic}",
                    "recommendations": ["暂无具体标准，请参考行业通用最佳实践"],
                }
            )
        except Exception as e:
            return ToolResult.fail(f"行业标准查询失败: {e}")

    async def _generate_standards(self, industry: str, topic: str) -> dict:
        """使用 LLM 生成行业标准。"""
        prompt = f"""请提供 {industry} 行业关于 "{topic}" 的标准和最佳实践。

返回 JSON 格式：
{{
    "title": "标题",
    "recommendations": ["建议1", "建议2"],
    "common_mistakes": ["常见错误1", "常见错误2"],
    "best_practices": ["最佳实践1", "最佳实践2"]
}}

返回且仅返回 JSON 对象。"""

        response = await self._llm.generate(prompt)
        import json

        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except Exception:
            return {"title": f"{industry} - {topic}", "recommendations": []}
