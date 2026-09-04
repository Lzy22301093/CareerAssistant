"""Plan 模型测试 — 版本感知裁剪（v3 线性流水线架构后独立模块）。"""

from app.graph.plan import (
    TASK_PENDING,
    artifact_freshness,
    build_plan,
)


def _fresh_state(**over):
    """全新会话：有 JD+简历文本，无任何产物。"""
    s = {
        "intent": "upload_jd",
        "user_message": "帮我分析",
        "jd_text": "职位描述" + "J" * 80,
        "resume_text": "工作经历" + "R" * 80,
        "jd_input_version": 1,
        "profile_input_version": 1,
    }
    s.update(over)
    return s


def _complete_state(jiv=1, piv=1, **over):
    """完整会话：全部产物存在且版本匹配。"""
    s = _fresh_state()
    s.update({
        "intent": "fallback",
        "jd_analysis": {"job_title": "x"},
        "jd_analyzed_version": jiv,
        "profile": {"name": "x"},
        "profile_analyzed_version": piv,
        "gap_analysis": {"overall_score": 80},
        "gap_based_jd": jiv,
        "gap_based_profile": piv,
        "resume_content": {"sections": [{"title": "t", "content": "c"}]},
        "content_based_jd": jiv,
        "content_based_profile": piv,
        "interview_questions": {"questions": []},
        "interview_based_jd": jiv,
        "interview_based_profile": piv,
        "render_config": {"template": "t"},
    })
    s.update(over)
    return s


def _exec(plan):
    return sorted(plan.executed_types)


ALL_TASKS = [
    "analyze_jd", "extract_profile", "gap_analysis", "generate_content",
    "generate_interview", "render_html", "review_content", "review_interview",
]


# === artifact_freshness 测试 ===


class TestArtifactFreshness:

    def test_old_session_without_version_fields_is_valid(self):
        """旧会话无版本字段 → 视为有效（兼容语义不触发全量重算）。"""
        state = _complete_state()
        for k in ("jd_analyzed_version", "profile_analyzed_version", "gap_based_jd",
                  "gap_based_profile", "content_based_jd", "content_based_profile",
                  "interview_based_jd", "interview_based_profile"):
            state.pop(k, None)
        assert all(artifact_freshness(state).values())

    def test_error_artifact_is_stale(self):
        fresh = artifact_freshness(_complete_state(gap_analysis={"_error": "boom"}))
        assert fresh["gap_analysis"] is False

    def test_version_mismatch_cascades(self):
        """换 JD：jd/gap/content/interview 过期，profile 与 render 不受影响。"""
        fresh = artifact_freshness(_complete_state(jd_input_version=2))
        assert fresh["jd_analysis"] is False
        assert fresh["profile"] is True
        assert fresh["gap_analysis"] is False
        assert fresh["resume_content"] is False
        assert fresh["interview_questions"] is False
        assert fresh["render_config"] is True  # 不依赖输入版本

    def test_fresh_complete_state(self):
        """完整状态且版本匹配 → 全部新鲜。"""
        fresh = artifact_freshness(_complete_state())
        assert all(fresh.values())


# === build_plan 裁剪场景 ===


class TestBuildPlan:

    def test_fresh_full_run(self):
        plan = build_plan(_fresh_state())
        assert plan.source == "full_pipeline"
        assert _exec(plan) == sorted(ALL_TASKS)
        assert plan.post_route == "end"

    def test_all_fresh_nothing_to_do(self):
        plan = build_plan(_complete_state())
        assert not plan.executable()
        assert all(t.status == "skipped_fresh" for t in plan.tasks)
        assert plan.post_route == "clarifier"

    def test_content_edit_forces_regeneration(self):
        plan = build_plan(_complete_state(intent="content_edit"))
        assert _exec(plan) == [
            "generate_content", "render_html", "review_content", "review_interview",
        ]
        assert plan.post_route == "end"

    def test_render_edit_minimal(self):
        plan = build_plan(_complete_state(intent="render_edit"))
        assert _exec(plan) == ["render_html", "review_interview"]

    def test_gap_rerun_minimal(self):
        plan = build_plan(_complete_state(intent="gap_analysis"))
        assert _exec(plan) == ["gap_analysis"]
        assert plan.post_route == "clarifier"

    def test_jd_change_full_cascade(self):
        """换 JD → 提取/差距/内容级联重算 + 评审渲染失效。"""
        plan = build_plan(_complete_state(jd_input_version=2, intent="upload_jd"))
        assert _exec(plan) == [
            "analyze_jd", "gap_analysis", "generate_content", "generate_interview",
            "render_html", "review_content", "review_interview",
        ]

    def test_upload_jd_partial_plan(self):
        plan = build_plan(_fresh_state(resume_text=""))
        assert plan.source == "partial_extract"
        # JD 已有文本 → jd_available=True，但 profile 不可用 → 只跑 extract_profile
        assert _exec(plan) == ["extract_profile"]
        assert plan.post_route == "clarifier"

    def test_no_inputs_returns_none(self):
        assert build_plan(_fresh_state(jd_text="", resume_text="")) is None

    def test_gap_analysis_missing_inputs_returns_none(self):
        """显式编辑意图前置不满足 → None → 旧路由接管。"""
        assert build_plan(_fresh_state(resume_text="", intent="gap_analysis")) is None

    def test_render_edit_without_content_returns_none(self):
        assert build_plan(_fresh_state(intent="render_edit")) is None

    def test_skipped_tasks_carry_reason(self):
        plan = build_plan(_complete_state(intent="render_edit"))
        skipped = [t for t in plan.tasks if t.status == "skipped_fresh"]
        assert all(t.skip_reason == "artifact_fresh" for t in skipped)
        assert plan.to_display()  # 前端展示可用

    def test_plan_display_format(self):
        """to_display 返回可用的前端展示格式。"""
        plan = build_plan(_complete_state(intent="content_edit"))
        display = plan.to_display()
        assert isinstance(display, list)
        assert all("task" in d and "status" in d for d in display)
