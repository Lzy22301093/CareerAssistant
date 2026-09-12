"""Tests for ResumeWizardService（简历生成区：草稿 / STAR / 生成导出 / 证件照）。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import User
from app.models.schemas import (
    ExperienceGenerateRequest,
    ExperienceStructureRequest,
    ResumeDraftSave,
    StarRequest,
    StarResultItem,
    WizardExperienceCreate,
    WizardGenerateRequest,
)
from app.services.resume_wizard_service import ResumeWizardService, WizardError


STAR_RESP = {
    "items": [
        {
            "exp_type": "项目",
            "company": "省数学竞赛",
            "title": "参赛选手",
            "situation": "全省高校参赛，题目难度高、覆盖面广",
            "task": "在竞赛中取得省级二等奖",
            "action": "系统学习高等数学、线性代数与概率论",
            "result": "获得省级二等奖",
        }
    ]
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
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _svc() -> ResumeWizardService:
    return ResumeWizardService()


# ---- 暂存退出 ----

def test_draft_save_load_clear(db_session: Session):
    svc = _svc()
    svc.save_draft(db_session, 1, ResumeDraftSave(step=3, data={"direction": "后端"}))
    d = svc.load_draft(db_session, 1)
    assert d["step"] == 3 and d["data"]["direction"] == "后端"
    # 覆盖
    svc.save_draft(db_session, 1, ResumeDraftSave(step=5, data={"x": 1}))
    assert svc.load_draft(db_session, 1)["step"] == 5
    svc.clear_draft(db_session, 1)
    assert svc.load_draft(db_session, 1)["step"] is None


def test_load_draft_none(db_session: Session):
    assert _svc().load_draft(db_session, 1)["step"] is None


# ---- 03 自然语言结构化 / AI 生成 ----

EXP_BATCH_RESP = {
    "items": [
        {
            "exp_type": "竞赛",
            "company": "全国大学生数学建模竞赛",
            "title": "建模手",
            "duration": "2024.06-2024.09",
            "duty": "负责数据清洗与模型搭建，完成指标预测",
            "achievement": "获省级二等奖",
        }
    ]
}


@pytest.mark.asyncio
async def test_structure_experiences_from_nl(db_session: Session):
    llm = MockLLM([json.dumps(EXP_BATCH_RESP, ensure_ascii=False)])
    req = ExperienceStructureRequest(
        text="参加了数学建模竞赛，负责数据处理，最后拿了省二",
        directions=["算法工程师"],
    )
    items = await _svc().structure_experiences(db_session, 1, req, llm)
    assert len(items) == 1
    assert items[0].exp_type == "竞赛"
    assert items[0].company
    assert items[0].duty
    assert items[0].achievement


@pytest.mark.asyncio
async def test_structure_experiences_empty_text(db_session: Session):
    with pytest.raises(WizardError):
        await _svc().structure_experiences(
            db_session, 1, ExperienceStructureRequest(text="   "), MockLLM([])
        )


@pytest.mark.asyncio
async def test_generate_experiences(db_session: Session):
    llm = MockLLM([json.dumps(EXP_BATCH_RESP, ensure_ascii=False)])
    items = await _svc().generate_experiences(
        db_session, 1, ExperienceGenerateRequest(directions=["后端开发"], count=1), llm
    )
    assert len(items) == 1
    assert items[0].company and items[0].duty


@pytest.mark.asyncio
async def test_generate_experiences_empty_raises(db_session: Session):
    llm = MockLLM([json.dumps({"items": []}, ensure_ascii=False)])
    with pytest.raises(WizardError):
        await _svc().generate_experiences(db_session, 1, ExperienceGenerateRequest(), llm)


# ---- STAR 结构化 ----

@pytest.mark.asyncio
async def test_star_structuring(db_session: Session):
    llm = MockLLM([json.dumps(STAR_RESP, ensure_ascii=False)])
    req = StarRequest(experiences=[
        WizardExperienceCreate(exp_type="项目", company="省数学竞赛", title="参赛选手", duty="系统学习", achievement="省级二等奖")
    ])
    items = await _svc().star_structuring(db_session, 1, req, llm)
    assert len(items) == 1
    assert items[0].situation and items[0].action and items[0].result


@pytest.mark.asyncio
async def test_star_empty_returns_empty(db_session: Session):
    assert await _svc().star_structuring(db_session, 1, StarRequest(experiences=[]), MockLLM([])) == []


# ---- 生成与导出 ----

@pytest.mark.asyncio
async def test_generate_assemble_no_polish(db_session: Session):
    req = WizardGenerateRequest(
        title="我的新简历",
        basic_info={"name": "张三", "education": ["北京大学 本科"], "certifications": ["CET-6"], "skills": ["Python"]},
        directions=["后端开发工程师"],
        experiences=[
            StarResultItem(
                exp_type="实习", company="A公司", title="后端实习生", duration="2024.06-2024.09",
                situation="s", task="t", action="负责接口", result="延迟降低 30%",
                duty="负责接口", achievement="延迟降低 30%",
            )
        ],
        soft_info={"personality": "踏实", "self_eval": "认真负责", "disinterested": "不写进简历"},
        polish=False,
        import_to_library=False,
    )
    content, doc, version = await _svc().generate_resume(db_session, 1, req, None)
    titles = [s["title"] for s in content["sections"]]
    assert titles[0] == "基本信息"
    assert "求职意向" in titles
    assert "实习/工作经历" in titles
    assert "技能" in titles and "自我评价" in titles
    assert "软性信息" not in titles
    # 软性信息并入自我评价
    self_eval = next(s for s in content["sections"] if s["title"] == "自我评价")
    assert "认真负责" in self_eval["content"] and "踏实" in self_eval["content"]
    assert "不写进简历" not in self_eval["content"]
    # 无 Markdown 残留
    assert "###" not in content["raw_text"] and "- 情境" not in content["raw_text"]
    assert "2024.06-2024.09" in content["raw_text"]


def test_default_resume_title():
    assert ResumeWizardService.default_resume_title("张三", ["后端开发工程师"]) == "张三·后端开发工程师简历"
    assert ResumeWizardService.default_resume_title("张三", []) == "张三的简历"
    assert ResumeWizardService.default_resume_title(None, ["算法"]) == "算法简历"


@pytest.mark.asyncio
async def test_polish_preserves_section_count(db_session: Session):
    """润色不得丢模块。"""

    class PartialLLM:
        def __init__(self):
            self.n = 0

        async def chat(self, messages, **kwargs):
            from app.llm import Response
            self.n += 1
            # 故意只返回 content 字段（新协议）
            return Response(content=json.dumps({"content": f"润色后正文{self.n}"}, ensure_ascii=False))

    req = WizardGenerateRequest(
        title="张三·后端简历",
        basic_info={"name": "张三", "skills": ["Python"]},
        directions=["后端开发工程师"],
        experiences=[StarResultItem(exp_type="项目", company="X", title="成员", action="写代码", result="上线")],
        soft_info={"self_eval": "负责"},
        polish=True,
        import_to_library=False,
    )
    content, _, _ = await _svc().generate_resume(db_session, 1, req, PartialLLM())
    titles = [s["title"] for s in content["sections"]]
    assert "基本信息" in titles and "求职意向" in titles and "项目经历" in titles
    # 基本信息不被 LLM 改写
    basic_sec = next(s for s in content["sections"] if s["title"] == "基本信息")
    assert "张三" in basic_sec["content"]


@pytest.mark.asyncio
async def test_generate_import_to_library(db_session: Session):
    req = WizardGenerateRequest(title="导入简历", basic_info={"name": "李四"}, directions=["算法工程师"], polish=False, import_to_library=True)
    content, doc, version = await _svc().generate_resume(db_session, 1, req, None)
    assert doc is not None and doc.source == "generation"
    assert version is not None and version.document_id == doc.id
    assert content["sections"][0]["title"] == "基本信息"


@pytest.mark.asyncio
async def test_generate_polish_uses_llm(db_session: Session):
    llm = MockLLM([json.dumps({"content": "Python、FastAPI"}, ensure_ascii=False)])
    req = WizardGenerateRequest(
        basic_info={"name": "张三", "skills": ["Python"]},
        polish=True,
        import_to_library=False,
    )
    content, _, _ = await _svc().generate_resume(db_session, 1, req, llm)
    skills = next(s for s in content["sections"] if s["title"] == "技能")
    assert "FastAPI" in skills["content"]
    assert llm.call_count == 1


# ---- 证件照 ----

def test_photo_upload_and_get(db_session: Session, tmp_path):
    svc = _svc()
    photo = svc.upload_photo(db_session, 1, "me.jpg", b"\xff\xd8fake", upload_dir=str(tmp_path))
    assert photo.id
    assert svc.get_photo(db_session, 1).id == photo.id
    # 重传覆盖（user_id 唯一）
    photo2 = svc.upload_photo(db_session, 1, "me2.png", b"\x89PNG", upload_dir=str(tmp_path))
    assert photo2.id == photo.id
    assert svc.get_photo(db_session, 1).filename == "me2.png"


def test_photo_bad_format_rejected(db_session: Session, tmp_path):
    with pytest.raises(WizardError):
        _svc().upload_photo(db_session, 1, "a.exe", b"x", upload_dir=str(tmp_path))
