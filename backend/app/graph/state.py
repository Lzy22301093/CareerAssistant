"""GraphState — LangGraph 工作流状态定义。

每个 Agent 节点写入自己的字段，其他节点只读不写。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class GraphState(TypedDict, total=False):
    """LangGraph 工作流状态。

    字段按 Agent 职责划分，每个 Agent 只写入自己的字段。
    total=False 表示所有字段都是可选的（初始状态为空）。
    """

    # === 输入 ===
    user_message: str               # 用户当前消息
    session_id: str                 # 会话 ID
    jd_text: str                    # JD 原始文本（从文件解析或用户输入）
    resume_text: str                # 简历原始文本（从文件解析）

    # === 增量编辑（v3）：输入版本与下游基于版本 ===
    jd_input_version: int           # JD 文本代际（每次 JD 变化 +1）
    profile_input_version: int      # 简历文本代际（每次简历变化 +1）
    jd_analyzed_version: int        # jd_analysis 基于的 jd_input_version
    profile_analyzed_version: int   # profile 基于的 profile_input_version
    gap_based_jd: int               # gap_analysis 基于的 jd_input_version
    gap_based_profile: int          # gap_analysis 基于的 profile_input_version
    content_based_jd: int           # resume_content 基于的 jd_input_version
    content_based_profile: int      # resume_content 基于的 profile_input_version
    interview_based_jd: int         # interview_questions 基于的 jd_input_version
    interview_based_profile: int    # interview_questions 基于的 profile_input_version

    # === Planner 输出（v3：意图分类） ===
    route: str                      # 路由决策：jd_analyzer | profile_extractor | ...
    route_reason: str               # 路由原因
    intent: str                     # LLM 意图分类：upload_jd | upload_profile | ...
    intent_reason: str              # 意图分类理由
    execution_plan: list[str]       # 本轮执行计划（节点名序列，用于展示）

    # === JD Analyzer 输出 ===
    jd_analysis: dict[str, Any]     # JD 结构化分析结果

    # === Profile Extractor 输出 ===
    profile: dict[str, Any]         # 候选人画像

    # === Gap Analyzer 输出 ===
    gap_analysis: dict[str, Any]    # 差距分析结果

    # === Content Generator 输出 ===
    resume_content: dict[str, Any]  # 生成的简历内容
    content_iterations: int         # 内容生成迭代次数

    # === Reviewer 输出 ===
    review_result: dict[str, Any]   # 评审结果（score, issues, suggestions）

    # === HTML Renderer 输出 ===
    render_config: dict[str, Any]   # 渲染配置
    html_output: str                # 渲染后的 HTML

    # === Interview Q&A 输出 ===
    interview_questions: dict[str, Any]  # 面试题列表

    # === Interview Reviewer 输出 ===
    interview_review_result: dict[str, Any]  # 面试题评审结果（score, issues, suggestions）
    interview_iterations: int               # 面试题迭代次数

    # === Question（自由问答，v3）输出 ===
    answer: str                     # 基于当前状态回答用户问题

    # === Cover Letter（求职信，v3）输出 ===
    cover_letter: dict[str, Any]    # 求职信/打招呼文案 {channel, subject, body, ...}
    cover_letter_channel: str       # 用户选择的渠道：email | linkedin_message

    # === Clarifier 输出 ===
    clarification_question: str     # 需要向用户澄清的问题
    clarification_history: list[dict[str, Any]]  # 澄清对话历史
    ready_to_proceed: bool          # 澄清是否完成，可以继续处理

    # === Memory（v3） ===
    memory_summary: dict[str, Any]  # 跨会话注入的长期档案摘要（career_profile + preferences）

    # === 可观测（v3） ===
    workflow_trace: Annotated[list[dict[str, Any]], operator.add]  # 节点执行轨迹（累积）

    # === 通用 ===
    error: str                      # 错误信息
    messages: list[dict[str, Any]]  # 对话历史
