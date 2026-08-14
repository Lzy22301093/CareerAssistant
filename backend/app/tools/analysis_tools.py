"""分析工具集 — 日期解析、最佳实践、关键词优化。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.tools.base import Tool, ToolResult


class DateParserTool(Tool):
    """日期解析工具 — 统一各种日期格式。"""

    name = "date_parser"
    description = "解析各种日期格式，返回标准化的日期字符串"
    parameters = {
        "type": "object",
        "properties": {
            "date_string": {"type": "string", "description": "待解析的日期字符串"},
            "target_format": {"type": "string", "description": "目标格式，默认 YYYY-MM", "default": "%Y-%m"},
        },
        "required": ["date_string"],
    }

    # 常见日期格式
    FORMATS = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y年%m月%d日",
        "%Y年%m月",
        "%Y-%m",
        "%Y/%m",
        "%Y.%m",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %Y",
        "%b %Y",
        "%Y %B",
        "%Y %b",
    ]

    # 相对时间模式
    RELATIVE_PATTERNS = [
        (r"(\d+)\s*年前", lambda m: -int(m.group(1)) * 365),
        (r"(\d+)\s*月前", lambda m: -int(m.group(1)) * 30),
        (r"(\d+)\s*天前", lambda m: -int(m.group(1))),
        (r"至今|现在|present|current|now", lambda m: 0),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        date_string = kwargs.get("date_string", "")
        target_format = kwargs.get("target_format", "%Y-%m")

        if not date_string:
            return ToolResult.fail("date_string is required")

        # 尝试相对时间
        for pattern, calc in self.RELATIVE_PATTERNS:
            match = re.search(pattern, date_string, re.IGNORECASE)
            if match:
                days = calc(match)
                result_date = datetime.now().__add__(__import__("datetime").timedelta(days=days))
                return ToolResult.ok({
                    "original": date_string,
                    "parsed": result_date.strftime(target_format),
                    "is_relative": True,
                })

        # 尝试标准格式
        for fmt in self.FORMATS:
            try:
                parsed = datetime.strptime(date_string.strip(), fmt)
                return ToolResult.ok({
                    "original": date_string,
                    "parsed": parsed.strftime(target_format),
                    "is_relative": False,
                })
            except ValueError:
                continue

        return ToolResult.fail(f"无法解析日期: {date_string}")


class BestPracticesTool(Tool):
    """最佳实践工具 — 提供简历撰写和面试的最佳实践建议。"""

    name = "best_practices"
    description = "获取简历撰写和面试的最佳实践建议"
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "主题：resume_summary, work_experience, skills, education, interview_tips",
            },
            "industry": {"type": "string", "description": "行业（可选）", "default": ""},
        },
        "required": ["topic"],
    }

    # 最佳实践知识库
    PRACTICES = {
        "resume_summary": {
            "title": "个人简介/Summary 最佳实践",
            "tips": [
                "控制在 2-3 句话，50-100 字",
                "突出核心竞争力和职业目标",
                "使用动词开头，如'擅长'、'专注于'",
                "包含与目标职位相关的关键词",
                "避免使用第一人称'我'",
                "量化成就，如'5年经验'、'管理10人团队'",
            ],
            "example": "全栈工程师，5年 Python/React 开发经验，专注于高性能 Web 应用开发。主导过多个百万级用户产品的技术架构设计，擅长从0到1搭建技术体系。",
        },
        "work_experience": {
            "title": "工作经历最佳实践",
            "tips": [
                "使用 STAR 法则：情境(Situation)、任务(Task)、行动(Action)、结果(Result)",
                "每段经历 3-5 个要点",
                "量化成就：数字、百分比、金额",
                "使用强动词：主导、优化、重构、提升",
                "按时间倒序排列",
                "突出与目标职位相关的经验",
            ],
            "example": "• 主导微服务架构重构，将系统响应时间从 2s 优化至 200ms，QPS 提升 5 倍\n• 设计并实现自动化部署流程，部署时间从 2 小时缩短至 15 分钟\n• 带领 5 人团队完成核心业务模块开发，按时交付率 100%",
        },
        "skills": {
            "title": "技能板块最佳实践",
            "tips": [
                "分门别类：编程语言、框架、工具、软技能",
                "按熟练度排序：精通 > 熟悉 > 了解",
                "与 JD 关键词匹配",
                "避免列出过于基础的技能（如 Office）",
                "包含版本号（如 Python 3.11）",
                "适当包含软技能：团队协作、沟通能力",
            ],
            "example": "编程语言：Python（精通）、TypeScript（熟悉）、Go（了解）\n框架：FastAPI、Django、React、Vue.js\n数据库：PostgreSQL、MySQL、Redis、MongoDB\n工具：Docker、Kubernetes、Git、CI/CD",
        },
        "education": {
            "title": "教育背景最佳实践",
            "tips": [
                "最高学历放最前面",
                "包含学校、专业、学位、时间",
                "GPA 高于 3.5/4.0 可以写上",
                "列出相关课程（应届生）",
                "包含奖学金、竞赛获奖",
                "已工作多年可简化教育板块",
            ],
            "example": "XX大学 | 计算机科学与技术 | 本科 | 2018-2022\nGPA: 3.8/4.0 | 国家奖学金 | ACM 区域赛金奖",
        },
        "interview_tips": {
            "title": "面试技巧",
            "tips": [
                "准备 1-2 分钟的自我介绍",
                "用 STAR 法则回答行为面试题",
                "准备 3-5 个项目案例，能深入讲解",
                "了解目标公司和职位",
                "准备 3-5 个问题问面试官",
                "面试后发感谢邮件",
            ],
            "example": "自我介绍模板：面试官您好，我是XXX，毕业于XX大学计算机专业，有X年XX开发经验。上一份工作在XX公司担任XX职位，主要负责XX。我对贵公司的XX方向很感兴趣，希望能有机会加入团队。",
        },
    }

    async def execute(self, **kwargs) -> ToolResult:
        topic = kwargs.get("topic", "")
        industry = kwargs.get("industry", "")

        if not topic:
            return ToolResult.fail("topic is required")

        practice = self.PRACTICES.get(topic)
        if not practice:
            return ToolResult.fail(f"未知主题: {topic}，可用主题: {', '.join(self.PRACTICES.keys())}")

        result = dict(practice)
        if industry:
            result["industry_note"] = f"针对{industry}行业的建议可进一步细化"

        return ToolResult.ok(result)


class KeywordOptimizerTool(Tool):
    """关键词优化工具 — 分析和优化简历关键词。"""

    name = "keyword_optimizer"
    description = "分析简历关键词覆盖率，提供优化建议"
    parameters = {
        "type": "object",
        "properties": {
            "resume_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "简历中的关键词列表",
            },
            "jd_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "JD 中的关键词列表",
            },
        },
        "required": ["resume_keywords", "jd_keywords"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        resume_kw = set(kw.lower().strip() for kw in kwargs.get("resume_keywords", []))
        jd_kw = set(kw.lower().strip() for kw in kwargs.get("jd_keywords", []))

        if not jd_kw:
            return ToolResult.fail("jd_keywords is required")

        # 计算覆盖率
        matched = resume_kw & jd_kw
        missing = jd_kw - resume_kw
        extra = resume_kw - jd_kw

        coverage = len(matched) / len(jd_kw) * 100 if jd_kw else 0

        # 生成建议
        suggestions = []
        if missing:
            suggestions.append(f"建议添加以下关键词：{', '.join(list(missing)[:10])}")
        if coverage < 60:
            suggestions.append("关键词覆盖率较低，建议重点补充 JD 中的核心关键词")
        elif coverage < 80:
            suggestions.append("覆盖率中等，可以进一步优化")
        else:
            suggestions.append("关键词覆盖率良好")

        return ToolResult.ok({
            "coverage_rate": round(coverage, 1),
            "matched_keywords": list(matched),
            "missing_keywords": list(missing),
            "extra_keywords": list(extra),
            "suggestions": suggestions,
        })


class SimilarCasesTool(Tool):
    """相似案例工具 — 使用 RAG 检索相似的简历或面试案例。"""

    name = "similar_cases"
    description = "检索相似的简历或面试案例作为参考"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询"},
            "category": {
                "type": "string",
                "description": "案例类别：resume, interview",
                "enum": ["resume", "interview"],
            },
            "n_results": {"type": "integer", "description": "返回结果数量", "default": 3},
        },
        "required": ["query"],
    }

    def __init__(self, rag_service=None):
        self._rag = rag_service

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        category = kwargs.get("category")
        n_results = kwargs.get("n_results", 3)

        if not query:
            return ToolResult.fail("query is required")

        if self._rag is None:
            # RAG 服务未配置，返回空结果
            return ToolResult.ok({
                "cases": [],
                "message": "RAG 服务未配置，无法检索相似案例",
            })

        try:
            cases = self._rag.search_similar(
                query=query,
                n_results=n_results,
                category=category,
            )
            return ToolResult.ok({
                "cases": cases,
                "count": len(cases),
            })
        except Exception as e:
            return ToolResult.fail(f"检索失败: {str(e)}")
