"""Tests for SoftInfoService（阶段3 指令3-2：软性信息 AI 生成 + 保存）。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import ProfileItem, User
from app.models.schemas import SoftInfoSaveRequest
from app.services.soft_info_service import SoftInfoError, SoftInfoService

VALID_RESP = {
    "personality": "沉稳、有责任心，喜欢钻研技术边缘问题。",
    "vision": "希望在 3 年内成长为能独立负责模块的后端工程师。",
    "disinterested": "纯销售岗、高频出差与重复性录入工作。",
    "self_eval": "3 年 Python 后端经验，擅长 API 设计与性能优化，对团队协作负责。",
}


class MockLLM:
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
        ProfileItem(user_id=1, category="experience", title="后端", content="负责 API 开发", status="confirmed"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_generate_soft_info(db_session: Session):
    llm = MockLLM([json.dumps(VALID_RESP, ensure_ascii=False)])
    out = await SoftInfoService().generate_soft_info(db_session, 1, llm)
    assert out.personality
    assert out.self_eval
    assert out.vision
    assert out.disinterested
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_generate_empty_profile_raises(db_session: Session):
    db_session.query(ProfileItem).delete()
    db_session.commit()
    llm = MockLLM([json.dumps(VALID_RESP, ensure_ascii=False)])
    with pytest.raises(SoftInfoError, match="暂无已确认画像"):
        await SoftInfoService().generate_soft_info(db_session, 1, llm)


def test_save_soft_info_writes_soft_items(db_session: Session):
    payload = SoftInfoSaveRequest(
        personality="沉稳", vision="成长", disinterested="销售", self_eval="3 年 Python 经验"
    )
    items = SoftInfoService().save_soft_info(db_session, 1, payload)
    assert len(items) == 4
    assert all(i.category == "soft" and i.status == "confirmed" for i in items)
    by_title = {i.title: i for i in items}
    assert by_title["性格特点"].content == "沉稳"
    assert by_title["自我评价"].content == "3 年 Python 经验"
    # 每条带 user_input 证据
    for item in items:
        assert any(e.source_type == "user_input" for e in item.evidences)


def test_save_soft_info_empty_raises(db_session: Session):
    with pytest.raises(SoftInfoError, match="至少填写"):
        SoftInfoService().save_soft_info(db_session, 1, SoftInfoSaveRequest())


def test_save_soft_info_upserts_existing(db_session: Session):
    # 先写一条
    SoftInfoService().save_soft_info(db_session, 1, SoftInfoSaveRequest(self_eval="旧内容"))
    # 再写同标题 → 更新而非新增
    items = SoftInfoService().save_soft_info(db_session, 1, SoftInfoSaveRequest(self_eval="新内容"))
    assert len(items) == 1
    assert items[0].content == "新内容"
    count = (
        db_session.query(ProfileItem)
        .filter(ProfileItem.user_id == 1, ProfileItem.category == "soft", ProfileItem.title == "自我评价")
        .count()
    )
    assert count == 1
