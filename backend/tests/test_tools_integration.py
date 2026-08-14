"""Tool 层集成测试 — 调用真实 LLM 和存储。"""

import pytest
import tempfile
from pathlib import Path

from app.tools.file_tools import FileParserTool, TextCleanerTool
from app.tools.extract_tools import EntityExtractorTool, KeywordExtractorTool
from app.tools.render_tools import HtmlRendererTool, TemplateSearchTool
from app.tools.knowledge_tools import QuestionBankTool, IndustryStandardsTool
from app.tools.state_tools import StateReaderTool, StateWriterTool


# --- 文件解析集成测试 ---

class TestFileParserIntegration:
    """FileParserTool 真实文件测试。"""

    @pytest.mark.asyncio
    async def test_parse_real_text_file(self):
        """解析真实文本文件。"""
        tool = FileParserTool()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        ) as f:
            f.write("姓名：张三\n电话：13800138000\n邮箱：zhangsan@example.com")
            temp_path = f.name

        try:
            result = await tool.execute(file_path=temp_path)
            assert result.success is True
            assert "张三" in result.data["text"]
            assert result.data["length"] > 0
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self):
        """解析 Markdown 文件。"""
        tool = FileParserTool()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.md', delete=False, encoding='utf-8'
        ) as f:
            f.write("# 个人简历\n\n## 基本信息\n\n- 姓名：李四")
            temp_path = f.name

        try:
            result = await tool.execute(file_path=temp_path)
            assert result.success is True
            assert "个人简历" in result.data["text"]
        finally:
            Path(temp_path).unlink()


# --- 实体提取集成测试（真实 LLM）---

class TestEntityExtractorIntegration:
    """EntityExtractorTool 真实 LLM 测试。"""

    @pytest.fixture
    def tool(self):
        from app.llm import create_llm_provider
        return EntityExtractorTool(llm_provider=create_llm_provider())

    @pytest.mark.asyncio
    async def test_extract_from_resume_text(self, tool):
        """从简历文本中提取实体。"""
        text = """
        张三
        高级 Python 开发工程师
        手机：13800138000
        邮箱：zhangsan@example.com
        所在地：北京

        工作经历：
        2020-至今  字节跳动  高级后端工程师
        2018-2020  阿里巴巴  Python 开发工程师

        教育背景：
        北京大学  计算机科学与技术  硕士

        技能：
        Python, FastAPI, Django, MySQL, Redis, Docker, Kubernetes
        """

        result = await tool.execute(text=text)
        assert result.success is True

        entities = result.data.get("entities", {})
        # 验证提取结果
        assert entities.get("name") is not None, "应提取到姓名"
        assert "张三" in str(entities.get("name", "")), "姓名应为张三"

    @pytest.mark.asyncio
    async def test_extract_from_jd_text(self, tool):
        """从 JD 文本中提取实体。"""
        text = """
        【职位】高级 Python 开发工程师
        【公司】某互联网大厂
        【地点】上海
        【要求】
        - 3年以上 Python 开发经验
        - 熟悉 FastAPI/Django 框架
        - 有微服务架构经验
        """

        result = await tool.execute(
            text=text,
            entity_types=["company", "title", "location", "skill"]
        )
        assert result.success is True

        entities = result.data.get("entities", {})
        assert entities.get("title") is not None, "应提取到职位"


# --- 关键词提取集成测试（真实 LLM）---

class TestKeywordExtractorIntegration:
    """KeywordExtractorTool 真实 LLM 测试。"""

    @pytest.fixture
    def tool(self):
        from app.llm import create_llm_provider
        return KeywordExtractorTool(llm_provider=create_llm_provider())

    @pytest.mark.asyncio
    async def test_extract_keywords_from_resume(self, tool):
        """从简历中提取关键词。"""
        text = """
        5年 Python 后端开发经验，精通 FastAPI 和 Django。
        熟悉 MySQL、Redis、MongoDB 等数据库。
        有 Docker、Kubernetes 容器化部署经验。
        熟悉微服务架构、RESTful API 设计。
        了解 CI/CD 流程，使用过 Jenkins、GitLab CI。
        """

        result = await tool.execute(text=text, context="resume")
        assert result.success is True

        keywords = result.data.get("keywords", [])
        assert len(keywords) > 0, "应提取到关键词"

        # 验证包含关键技能
        kw_texts = [kw.get("keyword", "") for kw in keywords]
        assert any("Python" in kw for kw in kw_texts), "应包含 Python"
        assert any("FastAPI" in kw or "Django" in kw for kw in kw_texts), "应包含框架"

    @pytest.mark.asyncio
    async def test_extract_keywords_from_jd(self, tool):
        """从 JD 中提取关键词。"""
        text = """
        岗位要求：
        1. 计算机相关专业本科及以上学历
        2. 3年以上 Java/Python 开发经验
        3. 熟悉 Spring Boot 或 FastAPI 框架
        4. 熟悉 MySQL、Redis，了解数据库优化
        5. 有微服务、分布式系统开发经验
        """

        result = await tool.execute(
            text=text,
            max_keywords=10,
            context="job_description"
        )
        assert result.success is True

        keywords = result.data.get("keywords", [])
        assert len(keywords) > 0, "应提取到关键词"

        # 验证有摘要
        assert result.data.get("summary") is not None, "应有摘要"


# --- 模板渲染集成测试 ---

class TestHtmlRendererIntegration:
    """HtmlRendererTool 真实渲染测试。"""

    @pytest.mark.asyncio
    async def test_render_full_resume(self):
        """渲染完整简历。"""
        tool = HtmlRendererTool()
        data = {
            "name": "张三",
            "email": "zhangsan@example.com",
            "phone": "13800138000",
            "location": "北京",
            "title": "高级 Python 开发工程师",
            "summary": "5年 Python 后端开发经验，精通 FastAPI",
            "skills": ["Python", "FastAPI", "MySQL", "Redis", "Docker"],
            "experience": [
                {
                    "company": "字节跳动",
                    "title": "高级后端工程师",
                    "period": "2020-至今",
                    "description": "负责核心服务开发"
                }
            ],
            "education": [
                {
                    "school": "北京大学",
                    "degree": "硕士",
                    "major": "计算机科学与技术",
                    "period": "2014-2017"
                }
            ]
        }

        result = await tool.execute(template_name="modern", data=data)
        assert result.success is True

        html = result.data["html"]
        assert "张三" in html
        assert "字节跳动" in html
        assert "Python" in html
        assert "北京大学" in html

    @pytest.mark.asyncio
    async def test_render_classic_template(self):
        """渲染经典模板。"""
        tool = HtmlRendererTool()
        data = {
            "name": "李四",
            "email": "lisi@example.com",
            "skills": ["Java", "Spring Boot"],
        }

        result = await tool.execute(template_name="classic", data=data)
        assert result.success is True
        assert "李四" in result.data["html"]

    @pytest.mark.asyncio
    async def test_render_minimal_template(self):
        """渲染极简模板。"""
        tool = HtmlRendererTool()
        data = {
            "name": "王五",
            "summary": "全栈开发工程师",
        }

        result = await tool.execute(template_name="minimal", data=data)
        assert result.success is True
        assert "王五" in result.data["html"]


# --- 状态管理集成测试 ---

class _MockSessionStore:
    """模拟 SessionStore，提供 get_session/update_session 接口。"""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    async def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    async def update_session(self, session_id: str, data: dict):
        self._sessions[session_id] = data


class TestStateToolsIntegration:
    """StateTools 使用 mock session store 测试。"""

    @pytest.mark.asyncio
    async def test_write_and_read_state(self):
        """写入并读取状态。"""
        store = _MockSessionStore()
        session_id = "test-integration-session"

        # 先创建一个会话（需要有内容，空 dict 是 falsy）
        store._sessions[session_id] = {"_init": True}

        writer = StateWriterTool(session_store=store)
        reader = StateReaderTool(session_store=store)

        # 写入
        write_result = await writer.execute(
            session_id=session_id,
            key="test_key",
            value={"name": "张三", "age": 30},
            memory_type="short_term",
        )
        assert write_result.success is True

        # 读取
        read_result = await reader.execute(
            session_id=session_id,
            key="test_key",
            memory_type="short_term",
        )
        assert read_result.success is True
        assert read_result.data["value"]["name"] == "张三"
