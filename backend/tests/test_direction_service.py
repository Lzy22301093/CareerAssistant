"""Tests for DirectionService（阶段3 指令3-1：画像方向推荐 1-3）。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import ProfileItem, User
from app.models.schemas import DirectionCandidate
from app.services.direction_service import DirectionError, DirectionService

VALID_RESP = {
    "directions": [
        {"title": "后端开发工程师", "reason": "熟悉 Python 与服务端", "detail": "侧重 API/数据库"},
        {"title": "算法工程师", "reason": "数学与机器学习基础扎实", "detail": "侧重搜索/推荐"},
        {"title": "数据分析师", "reason": "沟通与数据敏感度佳", "detail": "侧重业务分析"},
    ]
}


class MockLLM:
    """可编程 Mock LLM：按调用序返回预设响应。"""

    def __init__(self, responses: list[str]):
        self._responses = responses
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        resp = self._responses[min(self.call_count, len(self._responses) - 1)]
        self.call_count += 1
        from app.llm import Response
        return Response(content=resp)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    session.add(User(username="u1", email="u1@test.com", hashed_password="x"))
    session.commit()
    session.add_all([
        ProfileItem(user_id=1, category="skill", title="Python", content="3 年", status="confirmed"),
        ProfileItem(user_id=1, category="education", title="本科", content="计算机", status="confirmed"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _svc() -> DirectionService:
    return DirectionService()


@pytest.mark.asyncio
async def test_recommend_returns_deduped_candidates(db_session: Session):
    llm = MockLLM([json.dumps(VALID_RESP, ensure_ascii=False)])
    out = await _svc().recommend_directions(db_session, 1, llm)
    assert len(out) == 3
    assert out[0]["title"] == "后端开发工程师"
    assert out[0]["reason"]
    assert "detail" in out[0]
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_recommend_dedupes_duplicate_titles(db_session: Session):
    dup = {
        "directions": [
            {"title": "后端开发工程师", "reason": "a", "detail": ""},
            {"title": "后端开发工程师", "reason": "b", "detail": ""},
            {"title": "算法工程师", "reason": "c", "detail": ""},
        ]
    }
    llm = MockLLM([json.dumps(dup, ensure_ascii=False)])
    out = await _svc().recommend_directions(db_session, 1, llm)
    assert len(out) == 2


@pytest.mark.asyncio
async def test_recommend_empty_profile_raises(db_session: Session):
    # 清空画像条目 → 无已确认画像
    db_session.query(ProfileItem).delete()
    db_session.commit()
    llm = MockLLM([json.dumps(VALID_RESP, ensure_ascii=False)])
    with pytest.raises(DirectionError, match="暂无已确认画像"):
        await _svc().recommend_directions(db_session, 1, llm)


@pytest.mark.asyncio
async def test_recommend_invalid_llm_output_raises(db_session: Session):
    # 全部输出非法 → ainvoke_json_with_schema 抛 ValueError → 服务转 DirectionError
    llm = MockLLM(["坏数据", "更坏"])
    with pytest.raises(ValueError):
        await _svc().recommend_directions(db_session, 1, llm)


def test_confirm_saves_directions_as_target_items(db_session: Session):
    selected = [
        DirectionCandidate(title="后端开发工程师", reason="熟悉 Python", detail=""),
        DirectionCandidate(title="算法工程师", reason="数学好", detail=""),
        DirectionCandidate(title="数据分析师", reason="沟通佳", detail=""),
    ]
    items = _svc().confirm_directions(db_session, 1, selected)
    assert len(items) == 3
    assert all(i.category == "target" and i.status == "confirmed" for i in items)
    # 每条挂了 user_input 证据
    for item in items:
        assert any(e.source_type == "user_input" for e in item.evidences)


def test_confirm_rejects_more_than_three(db_session: Session):
    selected = [
        DirectionCandidate(title=f"方向{i}", reason="r", detail="")
        for i in range(5)
    ]
    with pytest.raises(DirectionError, match="最多"):
        _svc().confirm_directions(db_session, 1, selected)


def test_confirm_rejects_empty(db_session: Session):
    with pytest.raises(DirectionError, match="至少选择"):
        _svc().confirm_directions(db_session, 1, [])


def test_confirm_idempotent_same_title(db_session: Session):
    sel = [DirectionCandidate(title="后端开发工程师", reason="r", detail="")]
    _svc().confirm_directions(db_session, 1, sel)
    items2 = _svc().confirm_directions(db_session, 1, sel)
    # 已存在同名 confirmed target 条目 → 不重复写
    assert len(items2) == 1
    count = (
        db_session.query(ProfileItem)
        .filter(ProfileItem.user_id == 1, ProfileItem.category == "target", ProfileItem.title == "后端开发工程师")
        .count()
    )
    assert count == 1
