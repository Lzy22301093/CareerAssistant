"""API 集成测试 — 测试端到端 API 行为。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.sessions import get_store, _new_session_data
from app.llm.base import LLMProvider, Response, Role, Message
from app.models.schemas import SessionStage
from app.models.session_store import InMemorySessionStore


class MockLLM(LLMProvider):
    """模拟 LLM 提供商，用于 API 测试。"""

    def __init__(self):
        self._handlers: list[tuple[str, str]] = []
        self.default_response = '{"route": "jd_analyzer", "route_reason": "test"}'

    def when(self, contains: str, response: str):
        self._handlers.append((contains, response))
        return self

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        text = " ".join(m.content for m in messages if m.role == Role.SYSTEM or m.role == Role.USER)
        for contains, resp in self._handlers:
            if contains in text:
                return Response(content=resp)
        return Response(content=self.default_response)

    async def chat_stream(self, messages, **kwargs):
        yield Response(content=self.default_response)

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def mock_llm():
    """创建配置好的 MockLLM。"""
    llm = MockLLM()
    llm.when("职位描述", json.dumps({
        "job_title": "Python开发工程师",
        "company": "测试公司",
        "requirements": ["Python", "FastAPI"],
        "nice_to_have": ["Docker"],
        "keywords": ["python", "fastapi"],
    }, ensure_ascii=False))
    llm.when("简历", json.dumps({
        "name": "张三",
        "skills": ["Python", "FastAPI"],
        "experience": [],
        "projects": [],
        "education": [],
    }, ensure_ascii=False))
    llm.when("差距", json.dumps({
        "overall_score": 75,
        "strengths": ["Python"],
        "gaps": ["Docker"],
        "recommendations": ["学习Docker"],
    }, ensure_ascii=False))
    llm.when("简历内容", json.dumps({
        "sections": [{"title": "技能", "content": "Python, FastAPI"}],
        "raw_text": "技能：Python, FastAPI",
    }, ensure_ascii=False))
    llm.when("面试", json.dumps({
        "questions": [
            {
                "question": "介绍下FastAPI",
                "category": "技术",
                "difficulty": "medium",
                "answer_points": ["路由", "依赖注入"],
                "sample_answer": "FastAPI是一个现代Python Web框架",
            }
        ],
    }, ensure_ascii=False))
    return llm


@pytest.fixture(autouse=True)
async def reset_store():
    """每个测试前重置会话存储与图缓存（图缓存按 LLM 构建，测试间必须隔离）。"""
    import app.api.sessions as mod
    import app.graph.workflow as wf
    mod._store = InMemorySessionStore()
    wf._compiled_graph = None
    yield
    mod._store = None
    wf._compiled_graph = None


@pytest.fixture
async def client():
    """创建异步测试客户端。"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# === 测试用例 ===


class TestCreateSession:
    """测试创建会话。"""

    async def test_create_session(self, client: AsyncClient):
        resp = await client.post("/api/sessions/")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 36  # UUID


class TestGetSession:
    """测试获取会话。"""

    async def test_get_existing_session(self, client: AsyncClient):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["stage"] == SessionStage.INIT

    async def test_get_nonexistent_session(self, client: AsyncClient):
        resp = await client.get("/api/sessions/nonexistent")
        assert resp.status_code == 404


class TestListSessions:
    """测试历史会话列表接口。"""

    async def test_list_sessions(self, client: AsyncClient):
        await client.post("/api/sessions/")
        await client.post("/api/sessions/")

        resp = await client.get("/api/sessions/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert "session_id" in item
            assert "stage" in item
            assert "message_count" in item

    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/sessions/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestInterruptedRunPersistence:
    """处理中断时，已完成的节点结果应已即时落盘（历史刷新不丢）。"""

    async def test_partial_results_persisted_on_error(
        self, client: AsyncClient, mock_llm: MockLLM
    ):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        # 按消息内容区分调用：意图分类 → 正常；jd_analyzer → 正常；
        # 其余（clarifier 等）→ 抛异常，模拟处理中途失败
        class FakeBadRequest(Exception):
            status_code = 400

        class FailingLLM(MockLLM):
            def __init__(self):
                super().__init__()
                self.default_response = '{"route": "clarify"}'
                self.calls = 0

            async def chat(self, messages, **kwargs):
                self.calls += 1
                content = " ".join(m.content for m in messages)
                if "意图分类" in content:
                    return Response(content=json.dumps({
                        "intent": "upload_jd", "reason": "用户提供JD", "confidence": 0.9,
                    }))
                if "分析以下职位描述" in content:
                    return Response(content=json.dumps({
                        "job_title": "Python 开发工程师",
                        "company": "测试公司",
                        "requirements": [],
                        "keywords": ["python"],
                        "summary": "测试",
                    }, ensure_ascii=False))
                raise FakeBadRequest("模拟中途失败")

        with patch("app.api.sessions.create_llm_provider", return_value=FailingLLM()):
            resp = await client.post(
                f"/api/sessions/{session_id}/messages",
                json={"content": "职位描述：Python 开发工程师"},
            )

        events = _parse_sse(resp.text)
        event_types = [e["event"] for e in events]
        assert "error" in event_types  # 流程确实中断

        # 关键断言：已完成的 jd_analysis 已即时持久化，历史加载不丢
        session_resp = await client.get(f"/api/sessions/{session_id}")
        data = session_resp.json()
        assert data["jd_analysis"] is not None
        assert data["jd_analysis"]["job_title"] == "Python 开发工程师"


class TestSessionStatus:
    """测试会话状态。"""

    async def test_get_status(self, client: AsyncClient):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        resp = await client.get(f"/api/sessions/{session_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == SessionStage.INIT
        assert data["has_jd"] is False
        assert data["message_count"] == 0


class TestSendMessage:
    """测试发送消息（SSE 流式）。"""

    async def test_send_message_sse(self, client: AsyncClient, mock_llm: MockLLM):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        with patch("app.api.sessions.create_llm_provider", return_value=mock_llm):
            resp = await client.post(
                f"/api/sessions/{session_id}/messages",
                json={"content": "这是一份职位描述：Python开发"},
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # 解析 SSE 事件
        events = _parse_sse(resp.text)
        event_types = [e["event"] for e in events]
        assert "start" in event_types
        assert "done" in event_types

    async def test_send_message_updates_session(self, client: AsyncClient, mock_llm: MockLLM):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        with patch("app.api.sessions.create_llm_provider", return_value=mock_llm):
            await client.post(
                f"/api/sessions/{session_id}/messages",
                json={"content": "分析这份职位描述"},
            )

        resp = await client.get(f"/api/sessions/{session_id}")
        data = resp.json()
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["role"] == "user"


class TestFileUpload:
    """测试文件上传。"""

    async def test_upload_file(self, client: AsyncClient):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        resp = await client.post(
            f"/api/sessions/{session_id}/upload",
            files={"file": ("test.txt", b"Hello World", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file"]["filename"] == "test.txt"

    async def test_upload_to_nonexistent_session(self, client: AsyncClient):
        resp = await client.post(
            "/api/sessions/nonexistent/upload",
            files={"file": ("test.txt", b"Hello", "text/plain")},
        )
        assert resp.status_code == 404


class TestDeleteSession:
    """测试删除会话。"""

    async def test_delete_session(self, client: AsyncClient):
        create_resp = await client.post("/api/sessions/")
        session_id = create_resp.json()["session_id"]

        resp = await client.delete(f"/api/sessions/{session_id}")
        assert resp.status_code == 200

        # 确认已删除
        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient):
        resp = await client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 404


class TestHealthEndpoint:
    """测试健康检查端点。"""

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestExportResume:
    """测试简历导出端点。"""

    async def _seed_session(self, client: AsyncClient, sid: str):
        store = await get_store()
        await store.create(sid, {
            "session_id": sid,
            "stage": SessionStage.COMPLETED,
            "messages": [],
            "jd_analysis": {},
            "profile": {"name": "张三", "skills": ["Python"], "experience": []},
            "gap_analysis": {},
            "resume_content": {"sections": [{"title": "个人信息", "content": "张三"}]},
            "render_config": {"template": "modern"},
            "interview_questions": None,
            "uploaded_files": [],
        })

    async def test_export_html(self, client: AsyncClient):
        await self._seed_session(client, "export-1")
        resp = await client.post("/api/sessions/export-1/export", json={"format": "html"})
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "张三" in resp.text

    async def test_export_json(self, client: AsyncClient):
        await self._seed_session(client, "export-2")
        resp = await client.post("/api/sessions/export-2/export", json={"format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sections"][0]["title"] == "个人信息"

    async def test_export_markdown(self, client: AsyncClient):
        await self._seed_session(client, "export-3")
        resp = await client.post("/api/sessions/export-3/export", json={"format": "md"})
        assert resp.status_code == 200
        assert "个人信息" in resp.text

    async def test_export_without_resume(self, client: AsyncClient):
        create_resp = await client.post("/api/sessions/")
        sid = create_resp.json()["session_id"]
        resp = await client.post(f"/api/sessions/{sid}/export", json={"format": "html"})
        assert resp.status_code == 400

    async def test_export_bad_format(self, client: AsyncClient):
        await self._seed_session(client, "export-4")
        resp = await client.post("/api/sessions/export-4/export", json={"format": "pdf"})
        assert resp.status_code == 400


# === 辅助函数 ===


class TestClassifyError:
    """错误分类测试（v3）。"""

    def test_file_parse(self):
        from app.api.sessions import _classify_error
        category, hint = _classify_error(RuntimeError("PDF 解析失败"))
        assert category == "file_parse"
        assert hint

    def test_timeout(self):
        from app.api.sessions import _classify_error
        category, _ = _classify_error(TimeoutError("timeout"))
        assert category == "timeout"

    def test_format(self):
        from app.api.sessions import _classify_error
        category, _ = _classify_error(ValueError("JSON 解析错误"))
        assert category == "format"

    def test_rate_limit(self):
        from app.api.sessions import _classify_error

        class Fake429(Exception):
            status_code = 429

        category, _ = _classify_error(Fake429("too many"))
        assert category == "rate_limit"

    def test_server_error(self):
        from app.api.sessions import _classify_error

        class Fake500(Exception):
            status_code = 500

        category, _ = _classify_error(Fake500("boom"))
        assert category == "server"

    def test_unknown(self):
        from app.api.sessions import _classify_error
        category, _ = _classify_error(RuntimeError("某个未知错误"))
        assert category == "unknown"


def _parse_sse(text: str) -> list[dict]:
    """解析 SSE 响应文本为事件列表。"""
    events = []
    current_event = None
    current_data = None

    for line in text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            current_data = json.loads(line[6:])
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None

    return events
