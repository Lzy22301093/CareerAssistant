"""业务服务层测试。"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.models.redis_session import MemorySessionStore
from app.models.schemas import SessionStage


# === Mock LLM ===

class MockLLM:
    """模拟 LLM Provider。"""

    async def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096):
        """返回预设响应。"""
        content = messages[-1].content

        # 按优先级匹配（更具体的匹配放前面）
        # 1. 关键词提取（必须在 JD 分析之前，因为 prompt 也包含"职位描述"）
        if "提取关键词和短语" in content:
            return MagicMock(content='''{
                "keywords": [
                    {"keyword": "Python", "relevance": 0.95, "category": "skill"},
                    {"keyword": "FastAPI", "relevance": 0.85, "category": "technology"}
                ],
                "summary": "Python开发岗位"
            }''')

        # 2. JD 分析
        if "分析以下职位描述" in content:
            return MagicMock(content='''{
                "job_title": "Python 开发工程师",
                "company": "测试公司",
                "requirements": [
                    {"category": "skill", "content": "Python 3.10+", "importance": "high"},
                    {"category": "experience", "content": "3年以上开发经验", "importance": "high"}
                ],
                "nice_to_have": ["Docker经验"],
                "salary_range": "20-30K",
                "location": "北京",
                "summary": "招聘Python开发工程师"
            }''')

        # 3. 简历解析
        if "从以下简历文本中提取" in content:
            return MagicMock(content='''{
                "name": "张三",
                "email": "zhangsan@example.com",
                "phone": "13800138000",
                "education": [{"school": "北京大学", "degree": "硕士", "major": "计算机", "period": "2018-2021"}],
                "experience": [{"company": "字节跳动", "title": "工程师", "duration": "2021-至今", "highlights": ["核心服务开发"]}],
                "projects": [{"name": "项目A", "description": "描述", "tech_stack": ["Python"], "highlights": ["亮点"]}],
                "skills": ["Python", "FastAPI", "MySQL"],
                "certifications": [],
                "summary": "5年Python开发经验"
            }''')

        # 4. 差距分析
        if "分析候选人画像与职位要求之间的差距" in content:
            return MagicMock(content='''{
                "overall_score": 75.0,
                "gaps": [{"category": "skill", "requirement": "Docker", "current_level": "了解", "gap_severity": "major", "suggestion": "学习Docker"}],
                "strengths": ["Python经验丰富"],
                "recommendations": ["补充Docker经验"]
            }''')

        # 5. 简历内容生成
        if "生成一份专业的简历内容" in content:
            return MagicMock(content='''{
                "sections": [
                    {"title": "个人简介", "content": "5年Python开发经验"},
                    {"title": "专业技能", "content": "- Python\\n- FastAPI\\n- MySQL"},
                    {"title": "工作经历", "content": "### 字节跳动\\n- 核心服务开发"}
                ],
                "raw_text": "张三\\n5年Python开发经验"
            }''')

        return MagicMock(content='{}')

    async def generate(self, prompt, temperature=0.7, max_tokens=4096):
        """便捷方法。"""
        from app.llm.base import Message, Role
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return resp.content


# === SessionService 测试 ===

class TestSessionService:
    """SessionService 测试。"""

    @pytest.fixture
    def store(self):
        return MemorySessionStore()

    @pytest.fixture
    def service(self, store):
        from app.services.session_service import SessionService
        return SessionService(session_store=store)

    @pytest.mark.asyncio
    async def test_create_session(self, service):
        result = await service.create_session()
        assert "session_id" in result
        assert result["stage"] == SessionStage.INIT.value

    @pytest.mark.asyncio
    async def test_get_session(self, service):
        created = await service.create_session()
        session_id = created["session_id"]

        result = await service.get_session(session_id)
        assert result is not None
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, service):
        result = await service.get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session(self, service):
        created = await service.create_session()
        session_id = created["session_id"]

        updated = await service.update_session(session_id, {"stage": "has_jd"})
        assert updated is not None
        assert updated["stage"] == "has_jd"

    @pytest.mark.asyncio
    async def test_delete_session(self, service):
        created = await service.create_session()
        session_id = created["session_id"]

        assert await service.delete_session(session_id) is True
        assert await service.get_session(session_id) is None

    def test_add_and_get_messages(self, service):
        # 创建会话（同步方式）
        store = service._store
        session_data = store.create_session("test_msg", {"stage": "init"})
        session_id = session_data["session_id"]

        store.append_message(session_id, {"role": "user", "content": "你好"})
        store.append_message(session_id, {"role": "assistant", "content": "你好！有什么可以帮你的？"})

        session = store.get_session(session_id)
        messages = session.get("messages", [])
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_get_stage(self, service):
        store = service._store
        session_data = store.create_session("test_stage", {"stage": "init"})
        session_id = session_data["session_id"]

        assert service.get_stage(session_id) == SessionStage.INIT.value

        service.set_stage(session_id, "has_jd")
        assert service.get_stage(session_id) == "has_jd"


# === JDService 测试 ===

class TestJDService:
    """JDService 测试。"""

    @pytest.fixture
    def llm(self):
        return MockLLM()

    @pytest.fixture
    def service(self, llm):
        from app.services.jd_service import JDService
        return JDService(llm=llm)

    @pytest.mark.asyncio
    async def test_analyze(self, service):
        result = await service.analyze("招聘 Python 开发工程师，要求3年以上经验")
        assert result.job_title == "Python 开发工程师"
        assert len(result.requirements) > 0

    @pytest.mark.asyncio
    async def test_extract_keywords(self, service):
        keywords = await service.extract_keywords("Python 开发工程师，熟悉 FastAPI")
        assert len(keywords) > 0
        assert any("Python" in kw.get("keyword", "") for kw in keywords)

    @pytest.mark.asyncio
    async def test_process_with_text(self, service):
        result = await service.process(jd_text="招聘 Python 开发工程师")
        assert "analysis" in result
        assert "keywords" in result
        assert "jd_text" in result

    @pytest.mark.asyncio
    async def test_process_requires_input(self, service):
        with pytest.raises(ValueError, match="必须提供"):
            await service.process()

    @pytest.mark.asyncio
    async def test_parse_file(self, service):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("招聘 Python 开发工程师")
            temp_path = f.name

        try:
            text = await service.parse_file(temp_path)
            assert "Python" in text
        finally:
            Path(temp_path).unlink()


# === ResumeService 测试 ===

class TestResumeService:
    """ResumeService 测试。"""

    @pytest.fixture
    def llm(self):
        return MockLLM()

    @pytest.fixture
    def service(self, llm):
        from app.services.resume_service import ResumeService
        return ResumeService(llm=llm)

    @pytest.mark.asyncio
    async def test_extract_profile(self, service):
        profile = await service.extract_profile("张三，5年Python开发经验")
        assert profile.name == "张三"
        assert len(profile.skills) > 0

    @pytest.mark.asyncio
    async def test_analyze_gap(self, service):
        jd = {"job_title": "Python工程师", "requirements": [{"category": "skill", "content": "Docker", "importance": "high"}]}
        profile = {"name": "张三", "skills": ["Python"]}

        result = await service.analyze_gap(jd, profile)
        assert result.overall_score > 0
        assert len(result.gaps) > 0

    @pytest.mark.asyncio
    async def test_generate_content(self, service):
        jd = {"job_title": "Python工程师"}
        profile = {"name": "张三", "skills": ["Python"]}

        content = await service.generate_content(jd, profile)
        assert len(content.sections) > 0

    @pytest.mark.asyncio
    async def test_render_html(self, service):
        content = {
            "sections": [{"title": "技能", "content": "Python, FastAPI"}],
            "profile": {"name": "张三"},
        }
        html = await service.render_html(content)
        assert "张三" in html

    @pytest.mark.asyncio
    async def test_list_templates(self, service):
        templates = await service.list_templates()
        assert len(templates) > 0

    @pytest.mark.asyncio
    async def test_process_resume(self, service):
        result = await service.process_resume(
            resume_text="张三，5年Python开发经验",
            jd_analysis={"job_title": "Python工程师"},
        )
        assert "profile" in result
        assert "content" in result
        assert "html" in result


# === ExportService 测试 ===

class TestExportService:
    """ExportService 测试。"""

    @pytest.fixture
    def service(self, tmp_path):
        from app.services.export_service import ExportService
        return ExportService(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_export_html(self, service):
        path = await service.export_html("<h1>张三</h1>", "test_session")
        assert Path(path).exists()
        assert path.endswith(".html")

    @pytest.mark.asyncio
    async def test_export_json(self, service):
        content = {"name": "张三", "skills": ["Python"]}
        path = await service.export_json(content, "test_session")
        assert Path(path).exists()
        assert path.endswith(".json")

    @pytest.mark.asyncio
    async def test_export_markdown(self, service):
        content = {
            "profile": {"name": "张三"},
            "sections": [{"title": "技能", "content": "Python"}],
        }
        path = await service.export_markdown(content, "test_session")
        assert Path(path).exists()
        assert path.endswith(".md")

        md_text = Path(path).read_text(encoding="utf-8")
        assert "# 张三" in md_text

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, service):
        with pytest.raises(ValueError, match="不支持"):
            await service.export("pdf", {}, "", "test_session")
