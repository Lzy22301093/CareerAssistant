"""Tests for SectionRewriteService / SectionRewriterAgent（阶段2 指令2-2）。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents.section_rewriter import SectionRewriterAgent
from app.models.database import Base
from app.models.orm import User
from app.models.schemas import ResumeDocumentCreate, ResumeVersionCreate, ResumeSectionUpdate
from app.services.resume_library_service import ResumeLibraryError, ResumeLibraryService
from app.services.rewrite_schema import SectionRewriteOutput
from app.services.section_rewrite_service import (
    SectionRewriteError,
    SectionRewriteService,
    _clean_history,
    _find_fabricated_numbers,
    _numbers_in,
)

CONTENT = {
    "sections": [
        {"title": "教育经历", "content": "XX大学 计算机本科"},
        {"title": "工作经历", "content": "A公司 后端工程师"},
        {"title": "项目经历", "content": "负责检索问答系统"},
        {"title": "技能", "content": "Python, SQL"},
    ],
    "raw_text": "XX大学 计算机本科\nA公司 后端工程师\n负责检索问答系统\nPython, SQL",
}

PROFILE = {"name": "张三", "skills": ["Python", "SQL"], "experience": [{"title": "A公司 后端工程师"}]}


def _valid_llm_payload(with_fabrication: bool = False) -> str:
    rewrite = "主导检索问答系统建设，检索准确率提升40%" if with_fabrication else "主导检索问答系统建设，优化检索链路"
    return json.dumps(
        {
            "candidates": [
                {"rewrite": rewrite, "approach": "突出主导性与结果", "changes": ["改为主动语态"]},
                {"rewrite": "参与检索问答系统研发", "approach": "保守表述", "changes": []},
            ],
            "needs_source_confirmation": with_fabrication,
            "new_numbers": ["40%"] if with_fabrication else [],
            "new_claims": ["主导检索问答系统"] if with_fabrication else [],
            "advice": "建议核对数字来源" if with_fabrication else None,
        },
        ensure_ascii=False,
    )


class FakeLLM:
    """直接返回预设 JSON 的假 LLM（适配 BaseAgent.run 的调用面）。"""

    def __init__(self, payload: str):
        self.payload = payload
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        from app.llm.base import Response

        self.call_count += 1
        return Response(content=self.payload)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    session.add(User(username="u1", email="u1@test.com", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def section_row(db_session: Session):
    svc = ResumeLibraryService()
    doc = svc.create_document(db_session, 1, ResumeDocumentCreate(title="简历"))
    version = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT))
    # 给"技能"区域加个 boundingBox，验证采纳后元数据保留
    skill = version.sections[3]
    svc.update_section(db_session, 1, skill.id, ResumeSectionUpdate(bounding_box={"x": 1, "y": 2, "width": 3, "height": 4, "page": 1}))
    db_session.refresh(version)
    return version.sections[2]  # 项目经历


async def test_agent_parse_valid_json(db_session: Session, section_row):
    agent = SectionRewriterAgent(FakeLLM(_valid_llm_payload()))
    raw = await agent.run(
        section_title=section_row.title,
        section_type=section_row.section_type,
        section_text=section_row.content,
        resume_summary="摘要",
        profile_context=PROFILE,
        user_instruction="更突出",
        conversation_history=[],
    )
    output = SectionRewriteOutput.model_validate(raw)
    assert len(output.candidates) == 2
    assert output.candidates[0].approach == "突出主导性与结果"


async def test_generate_candidates_clean(db_session: Session, section_row):
    svc = SectionRewriteService(FakeLLM(_valid_llm_payload(with_fabrication=False)))
    result = await svc.generate_candidates(db_session, 1, section_row.id, "更突出")
    assert len(result["candidates"]) == 2
    assert result["needs_source_confirmation"] is False
    assert result["new_numbers"] == []
    assert result["candidates"][0]["new_numbers"] == []


async def test_generate_candidates_flags_fabricated_numbers(db_session: Session, section_row):
    svc = SectionRewriteService(FakeLLM(_valid_llm_payload(with_fabrication=True)))
    result = await svc.generate_candidates(db_session, 1, section_row.id, "加量化")
    first = result["candidates"][0]
    assert "40" in first["new_numbers"]  # 代码级比对兜底（LLM 自报 40%，归一为 40）
    assert result["needs_source_confirmation"] is True
    assert "40" in result["new_numbers"]
    # 第二条候选没有捏造数字
    assert result["candidates"][1]["new_numbers"] == []


async def test_identical_candidates_rejected(db_session: Session, section_row):
    payload = json.dumps(
        {"candidates": [{"rewrite": section_row.content, "approach": "没改", "changes": []}]},
        ensure_ascii=False,
    )
    svc = SectionRewriteService(FakeLLM(payload))
    with pytest.raises(SectionRewriteError):
        await svc.generate_candidates(db_session, 1, section_row.id, "改一下")


async def test_invalid_schema_rejected(db_session: Session, section_row):
    svc = SectionRewriteService(FakeLLM('{"oops": true}'))
    with pytest.raises(SectionRewriteError):
        await svc.generate_candidates(db_session, 1, section_row.id, "改一下")


def test_clean_history_filters_and_truncates():
    history = [
        {"role": "system", "content": "应被丢弃"},
        {"role": "user", "content": "x" * 900},
        {"role": "assistant", "content": "好的"},
        {"role": "weird", "content": "应被丢弃"},
        "不是字典",
    ]
    cleaned = _clean_history(history)
    assert len(cleaned) == 2
    assert cleaned[0]["role"] == "user" and len(cleaned[0]["content"]) == 500
    assert cleaned[1]["role"] == "assistant"


def test_find_fabricated_numbers():
    corpus_nums = _numbers_in("提升30%，团队5人，1.5年")  # {30, 5, 1.5}
    assert _find_fabricated_numbers("增长40%且40.5个点", corpus_nums) == ["40", "40.5"]
    # 140 不应让 40 判定为已存在（词元级比对）
    assert _find_fabricated_numbers("140人", corpus_nums) == ["140"]
    assert _find_fabricated_numbers("提升30%", corpus_nums) == []


async def test_adopt_creates_new_version_and_preserves_metadata(db_session: Session, section_row):
    lib = ResumeLibraryService()
    old_version_id = section_row.resume_version_id
    new_version = lib.adopt_section_rewrite(
        db_session, 1, old_version_id, section_row.id, "主导检索问答系统建设，优化检索链路"
    )
    # 新版本号自增、指针切换、旧版本保留
    assert new_version.version == 2
    doc = lib.get_document(db_session, 1, section_row.resume_version.document_id)
    assert doc.current_version_id == new_version.id
    assert lib.get_version(db_session, 1, old_version_id) is not None
    # 内容替换 + raw_text 重算
    content = json.loads(new_version.content_json)
    assert content["sections"][2]["content"] == "主导检索问答系统建设，优化检索链路"
    assert "主导检索问答系统" in content["raw_text"]
    assert "XX大学 计算机本科" in content["raw_text"]
    # 区域行继承：4 行、目标区域已替换、其它区域内容与 boundingBox 保留
    assert len(new_version.sections) == 4
    target = next(s for s in new_version.sections if s.sort_order == 2)
    assert target.content == "主导检索问答系统建设，优化检索链路"
    skill = next(s for s in new_version.sections if s.sort_order == 3)
    assert skill.content == "Python, SQL"
    assert json.loads(skill.bounding_box) == {"x": 1, "y": 2, "width": 3, "height": 4, "page": 1}
    # 旧版本区域未被改动
    old_skill = next(s for s in lib.get_version(db_session, 1, old_version_id).sections if s.sort_order == 3)
    assert old_skill.content == "Python, SQL"


async def test_adopt_rejects_foreign_section(db_session: Session, section_row):
    lib = ResumeLibraryService()
    other_doc = lib.create_document(db_session, 1, ResumeDocumentCreate(title="其它"))
    other_version = lib.add_version(db_session, 1, other_doc.id, ResumeVersionCreate(content=CONTENT))
    with pytest.raises(ResumeLibraryError):
        lib.adopt_section_rewrite(db_session, 1, other_version.id, section_row.id, "x")
