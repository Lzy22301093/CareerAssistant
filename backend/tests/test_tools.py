"""Tool 层测试。"""

import pytest
import tempfile
from pathlib import Path

from app.tools.base import Tool, ToolResult
from app.tools.file_tools import FileParserTool, TextCleanerTool
from app.tools.extract_tools import EntityExtractorTool, KeywordExtractorTool
from app.tools.render_tools import HtmlRendererTool, TemplateSearchTool
from app.tools.knowledge_tools import QuestionBankTool, IndustryStandardsTool
from app.tools.state_tools import StateReaderTool, StateWriterTool


class TestToolResult:
    """ToolResult 测试。"""

    def test_ok_result(self):
        result = ToolResult.ok({"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_fail_result(self):
        result = ToolResult.fail("error message")
        assert result.success is False
        assert result.data is None
        assert result.error == "error message"


class TestFileParserTool:
    """FileParserTool 测试。"""

    @pytest.mark.asyncio
    async def test_parse_text_file(self):
        tool = FileParserTool()

        # 创建临时文本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Hello, World!")
            temp_path = f.name

        try:
            result = await tool.execute(file_path=temp_path)
            assert result.success is True
            assert result.data["text"] == "Hello, World!"
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_parse_nonexistent_file(self):
        tool = FileParserTool()
        result = await tool.execute(file_path="/nonexistent/file.txt")
        assert result.success is False
        assert "文件不存在" in result.error

    @pytest.mark.asyncio
    async def test_parse_unsupported_type(self):
        tool = FileParserTool()

        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            temp_path = f.name

        try:
            result = await tool.execute(file_path=temp_path)
            assert result.success is False
        finally:
            Path(temp_path).unlink()


class TestTextCleanerTool:
    """TextCleanerTool 测试。"""

    @pytest.mark.asyncio
    async def test_basic_clean(self):
        tool = TextCleanerTool()
        result = await tool.execute(text="  Hello   World  ", mode="basic")
        assert result.success is True
        assert result.data["text"] == "Hello World"

    @pytest.mark.asyncio
    async def test_aggressive_clean(self):
        tool = TextCleanerTool()
        result = await tool.execute(text="Hello! @#$%^&*() World!", mode="aggressive")
        assert result.success is True
        # 激进模式会移除特殊字符
        assert "Hello" in result.data["text"]
        assert "World" in result.data["text"]


class TestHtmlRendererTool:
    """HtmlRendererTool 测试。"""

    @pytest.mark.asyncio
    async def test_render_modern_template(self):
        tool = HtmlRendererTool()
        data = {
            "name": "张三",
            "email": "zhangsan@example.com",
            "phone": "13800138000",
            "skills": ["Python", "FastAPI", "SQLAlchemy"],
            "summary": "5年Python开发经验",
        }
        result = await tool.execute(template_name="modern", data=data)
        assert result.success is True
        assert "张三" in result.data["html"]
        assert "Python" in result.data["html"]

    @pytest.mark.asyncio
    async def test_render_nonexistent_template(self):
        tool = HtmlRendererTool()
        result = await tool.execute(template_name="nonexistent", data={})
        assert result.success is False


class TestTemplateSearchTool:
    """TemplateSearchTool 测试。"""

    @pytest.mark.asyncio
    async def test_search_all_templates(self):
        tool = TemplateSearchTool()
        result = await tool.execute(style="all")
        assert result.success is True
        assert result.data["count"] == 3  # modern, classic, minimal

    @pytest.mark.asyncio
    async def test_search_by_style(self):
        tool = TemplateSearchTool()
        result = await tool.execute(style="modern")
        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["templates"][0]["name"] == "modern"


class TestQuestionBankTool:
    """QuestionBankTool 测试。"""

    @pytest.mark.asyncio
    async def test_search_technical_questions(self):
        tool = QuestionBankTool()
        result = await tool.execute(category="technical", count=2)
        assert result.success is True
        assert len(result.data["questions"]) <= 2

    @pytest.mark.asyncio
    async def test_search_by_topic(self):
        tool = QuestionBankTool()
        result = await tool.execute(topic="Python")
        assert result.success is True
        # 应该返回 Python 相关的题目
        for q in result.data["questions"]:
            assert "Python" in q.get("topic", "") or "Python" in q.get("question", "")


class TestIndustryStandardsTool:
    """IndustryStandardsTool 测试。"""

    @pytest.mark.asyncio
    async def test_query_tech_standards(self):
        tool = IndustryStandardsTool()
        result = await tool.execute(industry="tech", topic="简历格式")
        assert result.success is True
        assert "title" in result.data
        assert "recommendations" in result.data

    @pytest.mark.asyncio
    async def test_query_unknown_topic(self):
        tool = IndustryStandardsTool()
        result = await tool.execute(industry="tech", topic="未知主题")
        assert result.success is True


class TestToolRegistry:
    """工具注册表测试。"""

    def test_create_all_tools(self):
        from app.tools import create_all_tools

        tools = create_all_tools()
        assert len(tools) == 10  # 10 个工具

        # 检查工具名称
        tool_names = [t.name for t in tools]
        assert "file_parser" in tool_names
        assert "text_cleaner" in tool_names
        assert "entity_extractor" in tool_names
        assert "keyword_extractor" in tool_names
        assert "html_renderer" in tool_names
        assert "template_search" in tool_names
        assert "question_bank" in tool_names
        assert "industry_standards" in tool_names
        assert "state_reader" in tool_names
        assert "state_writer" in tool_names


class TestCompactContext:
    """上下文压缩测试（防 _error 数据污染下游生成）。"""

    def test_compact_profile_filters_error(self):
        from app.tools.context import compact_profile

        err_profile = {"_error": "file_parse_failed", "name": "", "skills": []}
        assert compact_profile(err_profile) == {}

    def test_compact_jd_filters_error(self):
        from app.tools.context import compact_jd

        assert compact_jd({"_error": "no_jd_text"}) == {}

    def test_compact_gap_filters_error(self):
        from app.tools.context import compact_gap

        assert compact_gap({"_error": "missing_inputs"}) == {}

    def test_compact_profile_keeps_valid(self):
        from app.tools.context import compact_profile

        profile = {"name": "张三", "skills": ["Python"], "experience": []}
        out = compact_profile(profile)
        assert out["name"] == "张三"
