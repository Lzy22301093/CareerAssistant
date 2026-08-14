"""分析工具集测试。"""

from __future__ import annotations

import pytest
from datetime import datetime

from app.tools.analysis_tools import (
    DateParserTool,
    BestPracticesTool,
    KeywordOptimizerTool,
    SimilarCasesTool,
)


# === DateParserTool 测试 ===


class TestDateParserTool:
    @pytest.mark.asyncio
    async def test_parse_iso_date(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="2024-01-15")
        assert result.success is True
        assert result.data["parsed"] == "2024-01"

    @pytest.mark.asyncio
    async def test_parse_slash_date(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="2024/01/15")
        assert result.success is True
        assert result.data["parsed"] == "2024-01"

    @pytest.mark.asyncio
    async def test_parse_chinese_date(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="2024年1月")
        assert result.success is True
        assert result.data["parsed"] == "2024-01"

    @pytest.mark.asyncio
    async def test_parse_month_year(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="2024-03")
        assert result.success is True
        assert result.data["parsed"] == "2024-03"

    @pytest.mark.asyncio
    async def test_parse_relative_now(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="至今")
        assert result.success is True
        assert result.data["is_relative"] is True

    @pytest.mark.asyncio
    async def test_parse_invalid(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="不是日期")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_parse_empty(self):
        tool = DateParserTool()
        result = await tool.execute(date_string="")
        assert result.success is False


# === BestPracticesTool 测试 ===


class TestBestPracticesTool:
    @pytest.mark.asyncio
    async def test_resume_summary(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="resume_summary")
        assert result.success is True
        assert "tips" in result.data
        assert len(result.data["tips"]) > 0

    @pytest.mark.asyncio
    async def test_work_experience(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="work_experience")
        assert result.success is True
        assert "example" in result.data

    @pytest.mark.asyncio
    async def test_skills(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="skills")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_education(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="education")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_interview_tips(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="interview_tips")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unknown_topic(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="unknown")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_with_industry(self):
        tool = BestPracticesTool()
        result = await tool.execute(topic="resume_summary", industry="互联网")
        assert result.success is True
        assert "industry_note" in result.data


# === KeywordOptimizerTool 测试 ===


class TestKeywordOptimizerTool:
    @pytest.mark.asyncio
    async def test_full_coverage(self):
        tool = KeywordOptimizerTool()
        result = await tool.execute(
            resume_keywords=["Python", "FastAPI", "Docker"],
            jd_keywords=["Python", "FastAPI", "Docker"],
        )
        assert result.success is True
        assert result.data["coverage_rate"] == 100.0
        assert len(result.data["missing_keywords"]) == 0

    @pytest.mark.asyncio
    async def test_partial_coverage(self):
        tool = KeywordOptimizerTool()
        result = await tool.execute(
            resume_keywords=["Python", "FastAPI"],
            jd_keywords=["Python", "FastAPI", "Docker", "Kubernetes"],
        )
        assert result.success is True
        assert result.data["coverage_rate"] == 50.0
        assert "docker" in result.data["missing_keywords"]
        assert "kubernetes" in result.data["missing_keywords"]

    @pytest.mark.asyncio
    async def test_no_coverage(self):
        tool = KeywordOptimizerTool()
        result = await tool.execute(
            resume_keywords=["Java", "Spring"],
            jd_keywords=["Python", "FastAPI"],
        )
        assert result.success is True
        assert result.data["coverage_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_jd(self):
        tool = KeywordOptimizerTool()
        result = await tool.execute(
            resume_keywords=["Python"],
            jd_keywords=[],
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_extra_keywords(self):
        tool = KeywordOptimizerTool()
        result = await tool.execute(
            resume_keywords=["Python", "FastAPI", "React", "Vue"],
            jd_keywords=["Python", "FastAPI"],
        )
        assert result.success is True
        assert "react" in result.data["extra_keywords"]
        assert "vue" in result.data["extra_keywords"]


# === SimilarCasesTool 测试 ===


class TestSimilarCasesTool:
    @pytest.mark.asyncio
    async def test_no_rag_service(self):
        """RAG 服务未配置时返回空结果。"""
        tool = SimilarCasesTool()
        result = await tool.execute(query="Python 工程师")
        assert result.success is True
        assert result.data["cases"] == []

    @pytest.mark.asyncio
    async def test_with_rag_service(self):
        """使用 RAG 服务。"""
        from app.rag.service import RAGService
        rag = RAGService()
        rag.add_case("c1", "Python 工程师简历", {"category": "resume"})

        tool = SimilarCasesTool(rag_service=rag)
        result = await tool.execute(query="Python", category="resume")
        assert result.success is True
        assert result.data["count"] > 0

    @pytest.mark.asyncio
    async def test_empty_query(self):
        tool = SimilarCasesTool()
        result = await tool.execute(query="")
        assert result.success is False
