"""Plan（Track B / B1）— planner-executor 架构的任务计划模型。

内容：
- Task / Plan：任务 DAG 数据结构（id/type/depends_on/status）
- TASK_META / INVALIDATED_BY：任务的产物字段、版本依赖与失效级联关系，
  prune_plan 与 artifact_freshness 共用同一套版本判断（4.6 的关键约束）
- artifact_freshness：_version_aware_has 的字段级重构（edges.py 复用，避免两套逻辑漂移）
- build_plan：意图 → 模板（force 集 + 前置条件）→ 版本感知裁剪
- expand_plan_sequence / simulate_legacy_sequence：影子对比与路由对齐测试（4.5 S1/S2）

裁剪语义（与固定图行为等价性的核心）：
1. 显式编辑意图强制重跑对应任务（gap_analysis/content_edit/render_edit 的 force 集）
2. 版本过期或产物无效 → 任务执行
3. 失效级联：内容重生成 → 评审/渲染失效；面试题/渲染重生成 → 面试题评审失效
4. 已知刻意改进：interview_questions 的裁剪是版本感知的（换 JD 会重生成），
   固定图 parallel_post 内部只做有效性检查（换 JD 后遗留旧面试题）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.state import GraphState

logger = logging.getLogger(__name__)

# === 任务状态 ===
TASK_PENDING = "pending"
TASK_SKIPPED = "skipped_fresh"


@dataclass
class Task:
    """计划中的一个任务：对应固定图中的一个业务节点。"""

    id: str
    type: str                      # analyze_jd / extract_profile / gap_analysis / ...
    depends_on: list[str] = field(default_factory=list)
    status: str = TASK_PENDING
    skip_reason: str = ""

    def skip(self, reason: str) -> None:
        self.status = TASK_SKIPPED
        self.skip_reason = reason


@dataclass
class Plan:
    """一次请求的任务计划（模板实例 + 裁剪结果）。"""

    intent: str
    source: str                     # 模板名（full_pipeline / partial_extract 等）
    tasks: list[Task] = field(default_factory=list)
    post_route: str = "clarifier"   # 计划执行完后的去向：end | clarifier

    @property
    def executed_types(self) -> set[str]:
        return {t.type for t in self.tasks if t.status == TASK_PENDING}

    def executable(self) -> bool:
        return bool(self.executed_types)

    def to_display(self) -> list[dict[str, str]]:
        """前端 execution_plan 展示用。"""
        return [
            {"task": t.type, "status": t.status, "reason": t.skip_reason}
            for t in self.tasks
        ]


# === 任务元数据（4.6）===

# produces: 任务产出的 state 字段；version_dep: 产物基于的输入版本
# - "jd_input"/"profile_input"：与当前输入版本比对
# - ("jd", "profile")：与 (jiv, piv) 组合比对
# - None：不依赖输入版本（render_config 只看有效性；review_* 不参与版本裁剪）
TASK_META: dict[str, dict[str, Any]] = {
    "analyze_jd":        {"produces": "jd_analysis",         "version_dep": "jd_input"},
    "extract_profile":   {"produces": "profile",             "version_dep": "profile_input"},
    "gap_analysis":      {"produces": "gap_analysis",        "version_dep": ("jd", "profile")},
    "generate_content":  {"produces": "resume_content",      "version_dep": ("jd", "profile")},
    "review_content":    {"produces": "review_result",       "version_dep": None},
    "generate_interview": {"produces": "interview_questions", "version_dep": ("jd", "profile")},
    "render_html":       {"produces": "render_config",       "version_dep": None},
    "review_interview":  {"produces": "interview_review_result", "version_dep": None},
}

# 失效级联：前置任务实际执行 → 本任务产物逻辑失效，即使版本字段未变
INVALIDATED_BY: dict[str, list[str]] = {
    "review_content":   ["generate_content"],   # 内容重生成 → 评审必须重跑
    "render_html":      ["generate_content"],   # 内容重生成 → 渲染配置失效
    "review_interview": ["generate_interview", "render_html"],  # 到达即评审（固定图语义）
}

# 任务类型 → 固定图节点名（对齐测试与影子对比用）
TASK_NODE_NAME = {
    "analyze_jd": "jd_analyzer",
    "extract_profile": "profile_extractor",
    "gap_analysis": "gap_analyzer",
    "generate_content": "content_generator",
    "review_content": "reviewer",
    "generate_interview": "interview_qa",
    "render_html": "html_renderer",
    "review_interview": "interview_reviewer",
}

# 参与版本感知新鲜度判断的字段（artifact_freshness 的 key 集合）
FRESHNESS_FIELDS = (
    "jd_analysis", "profile", "gap_analysis", "resume_content",
    "render_config", "interview_questions",
)


# === 版本感知新鲜度（_version_aware_has 的字段级重构，edges.py 复用）===


def _valid(data: Any) -> bool:
    """数据有效性：非空、非错误状态（与 edges/nodes 的 _has_valid_data 一致）。"""
    if not isinstance(data, dict):
        return bool(data)
    if data.get("_error"):
        return False
    return bool(data)


def artifact_freshness(state: GraphState) -> dict[str, bool]:
    """字段级新鲜度：产物有效且基于的输入版本与当前一致。

    - jd/profile：与 jd_input_version / profile_input_version 比对
    - gap/content/interview：与 (jiv, piv) 组合比对
    - render_config：只看有效性（不依赖输入版本）
    - 旧会话（无版本字段）视为有效，避免触发全量重算（兼容语义与原实现一致）
    """
    jiv = state.get("jd_input_version", 0)
    piv = state.get("profile_input_version", 0)

    def _matched(version_field: str, expected: int) -> bool:
        if version_field not in state:
            return True  # 旧数据无版本字段 → 视为有效
        return state[version_field] == expected

    def _paired(base_jd: str, base_profile: str) -> bool:
        if base_jd not in state or base_profile not in state:
            return True
        return state[base_jd] == jiv and state[base_profile] == piv

    return {
        "jd_analysis": _valid(state.get("jd_analysis")) and _matched("jd_analyzed_version", jiv),
        "profile": _valid(state.get("profile")) and _matched("profile_analyzed_version", piv),
        "gap_analysis": _valid(state.get("gap_analysis"))
        and _paired("gap_based_jd", "gap_based_profile"),
        "resume_content": _valid(state.get("resume_content"))
        and _paired("content_based_jd", "content_based_profile"),
        "interview_questions": _valid(state.get("interview_questions"))
        and _paired("interview_based_jd", "interview_based_profile"),
        "render_config": _valid(state.get("render_config")),
    }


# === 意图模板注册表 ===

# 意图 → 强制重跑的任务集（显式编辑语义：用户明确要求重生成，不做版本裁剪）
INTENT_FORCE: dict[str, list[str]] = {
    "upload_jd": [],
    "upload_profile": [],
    "fallback": [],
    "gap_analysis": ["gap_analysis"],
    "content_edit": ["generate_content"],
    "render_edit": ["render_html"],
}

# 完整流水线模板（依赖已按拓扑序排列）
def _full_pipeline_tasks() -> list[Task]:
    return [
        Task(id="analyze_jd", type="analyze_jd"),
        Task(id="extract_profile", type="extract_profile"),
        Task(id="gap_analysis", type="gap_analysis",
             depends_on=["analyze_jd", "extract_profile"]),
        Task(id="generate_content", type="generate_content", depends_on=["gap_analysis"]),
        Task(id="review_content", type="review_content", depends_on=["generate_content"]),
        Task(id="generate_interview", type="generate_interview", depends_on=["generate_content"]),
        Task(id="render_html", type="render_html",
             depends_on=["review_content", "generate_interview"]),
        Task(id="review_interview", type="review_interview",
             depends_on=["render_html", "generate_interview"]),
    ]


def build_plan(state: GraphState) -> Plan | None:
    """根据状态（意图 + 输入 + 版本）构建裁剪后的任务计划。

    Returns:
        Plan：可执行或全部裁剪的计划；
        None：无法构建（输入完全缺失 / 意图不属于流水线意图），
              调用方回退 rule_based_route（第 4 层兜底）。
    """
    intent = state.get("intent") or "fallback"
    if intent not in INTENT_FORCE:
        return None

    jd_available = bool(state.get("jd_text")) or artifact_freshness(state)["jd_analysis"]
    profile_available = bool(state.get("resume_text")) or artifact_freshness(state)["profile"]

    if not jd_available and not profile_available:
        return None

    # 显式编辑意图的前置条件（与 edges.py 意图专用路由一致，不满足 → None → 旧路由澄清）
    if intent in ("gap_analysis", "content_edit"):
        fresh = artifact_freshness(state)
        if not (fresh["jd_analysis"] and fresh["profile"]):
            return None
    if intent == "render_edit" and not artifact_freshness(state)["resume_content"]:
        return None

    # 单边输入（仅输入类意图）：只计划可运行的那一侧提取任务，
    # 完成后交由澄清引导补充另一侧（对应固定图规则 4/5）
    if intent in ("upload_jd", "upload_profile", "fallback") and (
        not jd_available or not profile_available
    ):
        # 根据可用的文本决定提取哪个：
        # - 有 jd_text 但 jd 分析未完成 → 分析 JD
        # - 有 resume_text 但 profile 未提取 → 提取 profile
        # - 都有 → 并行处理（不应该进入这个分支）
        # - 都没有 → 无法处理（不应该进入这个分支）
        has_jd_text = bool(state.get("jd_text"))
        has_resume_text = bool(state.get("resume_text"))

        if has_jd_text and not jd_available:
            tasks = [Task(id="analyze_jd", type="analyze_jd")]
        elif has_resume_text and not profile_available:
            tasks = [Task(id="extract_profile", type="extract_profile")]
        elif not jd_available:
            tasks = [Task(id="analyze_jd", type="analyze_jd")]
        elif not profile_available:
            tasks = [Task(id="extract_profile", type="extract_profile")]
        else:
            # 两边都有且都已分析，不应该进入这个分支
            tasks = []
        plan = Plan(intent=intent, source="partial_extract", tasks=tasks, post_route="clarifier")
        _prune(plan, state)
        return plan

    plan = Plan(intent=intent, source="full_pipeline",
                tasks=_full_pipeline_tasks(), post_route="clarifier")
    _prune(plan, state)
    # 计划末段（面试题评审）实际执行 → 自然走 end（对应固定图 interview_reviewer → END）
    if "review_interview" in plan.executed_types:
        plan.post_route = "end"
    return plan


def _prune(plan: Plan, state: GraphState) -> None:
    """版本感知裁剪（计划阶段）：标记可跳过的任务。

    执行条件（按任务类别）：
    - 版本跟踪任务（jd/profile/gap/content/interview）：意图强制 OR 产物过期。
      级联失效由版本机制天然覆盖（换 JD → gap/content/interview 组合版本全过期）。
    - render_config（有效性跟踪）：额外被 generate_content 实际执行所失效
      （内容重生成 → 旧渲染配置作废）。
    - 未跟踪任务（review_*）：由失效级联决定——上游实际执行才需要评审，
      等价固定图"到达即评审"语义（render_edit 不重跑 reviewer 等）。
    拓扑序遍历一次完成（tasks 已按依赖拓扑排列）。
    """
    fresh = artifact_freshness(state)
    force = set(INTENT_FORCE.get(plan.intent, []))
    executed_by_type: dict[str, bool] = {}

    for task in plan.tasks:
        produces = TASK_META[task.type]["produces"]
        tracked = produces in FRESHNESS_FIELDS
        stale = tracked and not fresh[produces]
        invalidated = any(
            executed_by_type.get(upstream, False)
            for upstream in INVALIDATED_BY.get(task.type, [])
        )
        run = (task.type in force) or stale or invalidated

        if run:
            task.status = TASK_PENDING
        else:
            task.skip("artifact_fresh")
        executed_by_type[task.type] = run


# === 影子对比与对齐测试（4.5 S1/S2）===


def expand_plan_sequence(plan: Plan) -> list[str]:
    """计划将执行的业务节点序列（节点名映射，含 skipped 标注）。"""
    return [
        TASK_NODE_NAME[t.type]
        for t in plan.tasks
        if t.status == TASK_PENDING
    ]


def _business_capability_set(node_seq: list[str], state: GraphState) -> frozenset[str]:
    """把节点序列归一化为业务能力集合，消除容器节点与迭代噪音。

    - parallel_analysis → 展开为 jd_analyzer/profile_extractor（按文本存在性）
    - parallel_post → reviewer + interview_qa（interview_qa 仅在缺失时）
    """
    caps: set[str] = set()
    has_interview = _valid(state.get("interview_questions"))
    for node in node_seq:
        if node == "parallel_analysis":
            if state.get("jd_text"):
                caps.add("jd_analyzer")
            if state.get("resume_text"):
                caps.add("profile_extractor")
        elif node == "parallel_post":
            caps.add("reviewer")
            if not has_interview:
                caps.add("interview_qa")
        elif node in ("end", "clarifier", "planner"):
            continue
        else:
            caps.add(node)
    return frozenset(caps)


def plan_capability_set(plan: Plan) -> frozenset[str]:
    """计划侧的业务能力集合（review_content → reviewer 等映射后）。"""
    return frozenset(TASK_NODE_NAME[t.type] for t in plan.tasks if t.status == TASK_PENDING)


# 固定图的静态直连链：这些节点执行后不经规则路由，直接触发下游（add_edge 路径）
_STATIC_CHAINS: dict[str, list[str]] = {
    "content_generator": ["parallel_post", "html_renderer", "interview_reviewer"],
    "interview_qa": ["interview_reviewer"],
    "html_renderer": ["interview_reviewer"],
}


def simulate_legacy_sequence(state: GraphState, max_steps: int = 30) -> list[str]:
    """模拟固定图的节点执行序列（影子对比 / 对齐测试用）。

    两类走向：
    - planner 回流节点（jd/profile/parallel_analysis/gap）：规则路由逐步决策
    - 静态直连链（content→parallel_post→html_renderer→ireview 等）：
      按固定图 add_edge 直接展开，反思迭代按 proceed 假设
      （对齐对比关心能力集合，不关心反思迭代次数）
    """
    from app.graph.edges import rule_based_route  # 延迟导入避免环

    s: dict[str, Any] = dict(state)
    seq: list[str] = []
    for _ in range(max_steps):
        route = rule_based_route(s)
        if not route:
            break
        seq.append(route)
        if route in ("end", "clarifier", "question", "cover_letter"):
            break
        _apply_node_effect(s, route)
        # 静态直连链展开（固定图行为）
        for chained in _STATIC_CHAINS.get(route, []):
            seq.append(chained)
            _apply_node_effect(s, chained)
        if route in _STATIC_CHAINS:
            break  # 链尾必是 interview_reviewer → END（proceed 假设）
    return seq


def _apply_node_effect(s: dict[str, Any], node: str) -> None:
    """按 TASK_META 模拟节点写效果（占位产物 + 版本戳）。"""
    jiv = s.get("jd_input_version", 0)
    piv = s.get("profile_input_version", 0)
    ok: dict[str, Any] = {"_simulated": True}

    if node == "jd_analyzer":
        s["jd_analysis"] = dict(ok)
        s["jd_analyzed_version"] = jiv
    elif node == "profile_extractor":
        s["profile"] = dict(ok)
        s["profile_analyzed_version"] = piv
    elif node == "parallel_analysis":
        if s.get("jd_text"):
            s["jd_analysis"] = dict(ok)
            s["jd_analyzed_version"] = jiv
        if s.get("resume_text"):
            s["profile"] = dict(ok)
            s["profile_analyzed_version"] = piv
    elif node == "gap_analyzer":
        s["gap_analysis"] = dict(ok)
        s["gap_based_jd"], s["gap_based_profile"] = jiv, piv
    elif node == "content_generator":
        s["resume_content"] = {"sections": [{"title": "t", "content": "c1"}]}
        s["content_based_jd"], s["content_based_profile"] = jiv, piv
        s["content_iterations"] = s.get("content_iterations", 0) + 1
    elif node == "parallel_post":
        from app.graph.reflection import PASS_SCORE
        s["review_result"] = {"score": PASS_SCORE, "issues": [], "suggestions": []}
        if not _valid(s.get("interview_questions")):
            s["interview_questions"] = dict(ok)
            s["interview_based_jd"], s["interview_based_profile"] = jiv, piv
    elif node == "html_renderer":
        s["render_config"] = dict(ok)
    elif node == "interview_qa":
        s["interview_questions"] = dict(ok)
        s["interview_based_jd"], s["interview_based_profile"] = jiv, piv
        s["interview_iterations"] = s.get("interview_iterations", 0) + 1
    elif node == "interview_reviewer":
        s["interview_review_result"] = {"score": 100, "issues": [], "suggestions": []}
