"""GraphState — LangGraph 工作流状态定义。

每个 Agent 节点写入自己的字段，其他节点只读不写。
"""

from __future__ import annotations

from typing import Any, TypedDict


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

    # === Planner 输出 ===
    route: str                      # 路由决策：jd_analyzer | profile_extractor | ...
    route_reason: str               # 路由原因

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

    # === Clarifier 输出 ===
    clarification_question: str     # 需要向用户澄清的问题
    clarification_history: list[dict[str, Any]]  # 澄清对话历史
    ready_to_proceed: bool          # 澄清是否完成，可以继续处理

    # === 通用 ===
    error: str                      # 错误信息
    messages: list[dict[str, Any]]  # 对话历史
