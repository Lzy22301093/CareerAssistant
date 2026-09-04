"""GraphState — LangGraph 工作流状态定义。

每个 Agent 节点写入自己的字段，其他节点只读不写。
v4：移除 clarifier 相关字段，新增 execution_plan 驱动线性流水线。
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
    uploaded_files: list[dict[str, Any]]  # 上传的文件列表（filename, file_path, doc_type）

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

    # === Planner 输出（v4：意图 + 查表路由） ===
    route: str                      # 当前执行的节点名
    route_reason: str               # 路由原因
    intent: str                     # LLM 意图分类结果
    intent_reason: str              # 意图分类理由
    execution_plan: list[str]       # 执行计划（节点名序列，plan_advance 逐个弹出）

    # === JD Analyzer 输出 ===
    jd_analysis: dict[str, Any]     # JD 结构化分析结果

    # === Profile Extractor 输出 ===
    profile: dict[str, Any]         # 候选人画像

    # === Gap Analyzer 输出 ===
    gap_analysis: dict[str, Any]    # 差距分析结果（含 questions_to_ask）

    # === Content Generator 输出 ===
    resume_content: dict[str, Any]  # 生成的简历内容
    content_iterations: int         # 内容生成迭代次数

    # === HTML Renderer 输出 ===
    render_config: dict[str, Any]   # 渲染配置

    # === Interview Q&A 输出 ===
    interview_questions: dict[str, Any]  # 面试题列表
    interview_iterations: int            # 面试题迭代次数

    # === Question（自由问答，v3）输出 ===
    answer: str                     # 基于当前状态回答用户问题

    # === Cover Letter（求职信，v3）输出 ===
    cover_letter: dict[str, Any]    # 求职信/打招呼文案 {channel, subject, body, ...}
    cover_letter_channel: str       # 用户选择的渠道：email | linkedin_message

    # === Interview Record（面试记录，M3） ===
    interview_draft: dict[str, Any]  # 多轮追问收集的面试信息
    interview_recorded: bool         # 本轮面试记录是否已完成入库

    # === Memory（v3） ===
    memory_summary: dict[str, Any]  # 跨会话注入的长期档案摘要

    # === 可观测（v3） ===
    workflow_trace: Annotated[list[dict[str, Any]], operator.add]  # 节点执行轨迹（累积）

    # === 通用 ===
    error: str                      # 错误信息
    messages: list[dict[str, Any]]  # 对话历史
