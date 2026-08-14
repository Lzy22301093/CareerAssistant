"""节点函数 — 每个节点调用对应的 Agent。

节点函数签名：(state: GraphState) -> dict（返回要更新的字段）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.graph.state import GraphState

logger = logging.getLogger(__name__)


async def planner_node(state: GraphState, agents: dict) -> dict:
    """Planner 节点：使用规则引擎决定路由（无需 LLM 调用）。"""
    logger.info("[Node] Planner (Rule-based)")
    from app.graph.edges import rule_based_route

    route = rule_based_route(state)
    return {
        "route": route,
        "route_reason": f"规则引擎路由: {route}",
    }


async def jd_analyzer_node(state: GraphState, agents: dict) -> dict:
    """JD Analyzer 节点：分析职位描述。"""
    logger.info("[Node] JD Analyzer")
    agent = agents["jd_analyzer"]

    # 优先使用解析后的 JD 文本
    jd_text = state.get("jd_text", "")

    # 如果 JD 文本为空，检查是否有上传的文件但解析失败
    if not jd_text:
        uploaded_files = state.get("uploaded_files", [])
        if uploaded_files:
            logger.error(f"[Node] JD Analyzer: 有 {len(uploaded_files)} 个上传文件，但 JD 文本为空！文件解析可能失败。")
            return {"jd_analysis": {
                "_error": "file_parse_failed",
                "summary": "文件解析失败，请确认文件格式是否正确",
                "_hint": "请尝试：1) 复制 JD 文本直接粘贴 2) 使用文字型 PDF 3) 检查文件是否损坏"
            }}
        else:
            # 没有上传文件，尝试使用用户消息
            jd_text = state.get("user_message", "")
            if jd_text:
                logger.info("[Node] JD Analyzer: 使用 user_message 作为 JD 文本")
            else:
                logger.warning("[Node] JD Analyzer: 无 JD 文本可用")
                return {"jd_analysis": {
                    "_error": "no_jd_text",
                    "summary": "未提供职位描述文本",
                    "_hint": "请上传 JD 文件或直接粘贴职位描述"
                }}

    # 验证 JD 文本质量
    if len(jd_text) < 50:
        logger.warning(f"[Node] JD Analyzer: JD 文本过短 ({len(jd_text)} 字符)，可能解析不完整")

    logger.info(f"[Node] JD Analyzer: 使用 JD 文本 ({len(jd_text)} 字符)")
    logger.debug(f"[Node] JD Analyzer: JD 文本前 500 字符:\n{jd_text[:500]}")

    result = await agent.run(jd_text=jd_text)
    return {"jd_analysis": result}


async def profile_extractor_node(state: GraphState, agents: dict) -> dict:
    """Profile Extractor 节点：从简历提取候选人画像。"""
    logger.info("[Node] Profile Extractor")
    agent = agents["profile_extractor"]

    # 优先使用解析后的简历文本
    resume_text = state.get("resume_text", "")

    # 如果简历文本为空，检查是否有上传的文件但解析失败
    if not resume_text:
        uploaded_files = state.get("uploaded_files", [])
        if uploaded_files:
            logger.error(f"[Node] Profile Extractor: 有 {len(uploaded_files)} 个上传文件，但简历文本为空！文件解析可能失败。")
            return {"profile": {
                "_error": "file_parse_failed",
                "name": "",
                "skills": [],
                "experience": [],
                "projects": [],
                "education": [],
                "_hint": "文件解析失败，请确认：1) 文件是否为文字型 PDF（非扫描件）2) 文件是否损坏 3) 尝试重新上传"
            }}
        else:
            # 没有上传文件，尝试使用用户消息（可能是直接粘贴的简历）
            resume_text = state.get("user_message", "")
            if resume_text:
                logger.info("[Node] Profile Extractor: 使用 user_message 作为简历文本")
            else:
                logger.warning("[Node] Profile Extractor: 无简历文本可用")
                return {"profile": {
                    "_error": "no_resume_text",
                    "name": "",
                    "skills": [],
                    "experience": [],
                    "projects": [],
                    "education": [],
                    "_hint": "请上传简历文件或直接粘贴简历内容"
                }}

    # 验证简历文本质量
    if len(resume_text) < 50:
        logger.warning(f"[Node] Profile Extractor: 简历文本过短 ({len(resume_text)} 字符)，可能解析不完整")

    logger.info(f"[Node] Profile Extractor: 使用简历文本 ({len(resume_text)} 字符)")
    logger.debug(f"[Node] Profile Extractor: 简历文本前 500 字符:\n{resume_text[:500]}")

    result = await agent.run(resume_text=resume_text)

    # 检查解析结果质量
    if result.get("_parse_error"):
        logger.warning(f"[Node] Profile Extractor: JSON 解析失败，返回原始内容")
    elif not result.get("name") and not result.get("skills"):
        logger.warning(f"[Node] Profile Extractor: 解析结果缺少关键字段 (name, skills)")

    return {"profile": result}


async def gap_analyzer_node(state: GraphState, agents: dict) -> dict:
    """Gap Analyzer 节点：对比 JD 与画像。"""
    logger.info("[Node] Gap Analyzer")
    jd = state.get("jd_analysis") or {}
    profile = state.get("profile") or {}

    if not jd or not profile:
        logger.warning("[Node] Gap Analyzer skipped: jd_analysis or profile is empty")
        return {
            "gap_analysis": {
                "overall_score": 0,
                "strengths": [],
                "gaps": [],
                "recommendations": ["请先提供职位描述（JD）和个人简历"],
                "_error": "missing_inputs",
            }
        }

    agent = agents["gap_analyzer"]
    result = await agent.run(jd_analysis=jd, profile=profile)
    return {"gap_analysis": result}


async def content_generator_node(state: GraphState, agents: dict) -> dict:
    """Content Generator 节点：生成简历内容。如果是迭代，附带评审改进建议。"""
    logger.info("[Node] Content Generator")
    agent = agents["content_generator"]

    # 检查是否有评审反馈需要改进
    review_result = state.get("review_result", {})
    user_instructions = ""
    if review_result and review_result.get("suggestions"):
        from app.graph.reflection import build_reflection_prompt
        user_instructions = build_reflection_prompt(review_result)

    result = await agent.run(
        profile=state.get("profile", {}),
        jd_analysis=state.get("jd_analysis", {}),
        gap_analysis=state.get("gap_analysis", {}),
        user_instructions=user_instructions,
    )
    iterations = state.get("content_iterations", 0) + 1
    return {"resume_content": result, "content_iterations": iterations}


async def reviewer_node(state: GraphState, agents: dict) -> dict:
    """Reviewer 节点：评审简历内容质量。"""
    logger.info("[Node] Reviewer")
    agent = agents["reviewer"]
    result = await agent.run(
        resume_content=state.get("resume_content", {}),
        jd_analysis=state.get("jd_analysis", {}),
        profile=state.get("profile", {}),
    )
    return {"review_result": result}


async def html_renderer_node(state: GraphState, agents: dict) -> dict:
    """HTML Renderer 节点：生成渲染配置。"""
    logger.info("[Node] HTML Renderer")
    agent = agents["html_renderer"]
    result = await agent.run(
        resume_content=state.get("resume_content", {}),
    )
    return {"render_config": result}


async def interview_qa_node(state: GraphState, agents: dict) -> dict:
    """Interview Q&A 节点：生成面试题。如果是迭代，附带评审改进建议。"""
    logger.info("[Node] Interview Q&A")
    agent = agents["interview_qa"]

    # 检查是否有评审反馈需要改进
    review_result = state.get("interview_review_result", {})
    user_instructions = ""
    if review_result and review_result.get("suggestions"):
        from app.graph.reflection import build_reflection_prompt
        user_instructions = build_reflection_prompt(review_result, target="面试题")

    result = await agent.run(
        jd_analysis=state.get("jd_analysis", {}),
        profile=state.get("profile", {}),
        gap_analysis=state.get("gap_analysis", {}),
        user_instructions=user_instructions,
    )
    iterations = state.get("interview_iterations", 0) + 1
    return {"interview_questions": result, "interview_iterations": iterations}


async def interview_reviewer_node(state: GraphState, agents: dict) -> dict:
    """Interview Reviewer 节点：评审面试题质量。"""
    logger.info("[Node] Interview Reviewer")
    agent = agents["interview_reviewer"]
    result = await agent.run(
        interview_questions=state.get("interview_questions", {}),
        jd_analysis=state.get("jd_analysis", {}),
        profile=state.get("profile", {}),
    )
    return {"interview_review_result": result}


async def parallel_analysis_node(state: GraphState, agents: dict) -> dict:
    """并行执行 JD Analyzer 和 Profile Extractor。

    两个节点的输入完全独立（jd_text vs resume_text），输出也写入不同字段，
    因此可以安全地并行执行，节省一次完整的 LLM 调用时间。
    """
    logger.info("[Node] Parallel Analysis (JD + Profile)")

    tasks = []
    has_jd_text = bool(state.get("jd_text"))
    has_resume_text = bool(state.get("resume_text"))

    if has_jd_text:
        tasks.append(("jd", jd_analyzer_node(state, agents)))
    if has_resume_text:
        tasks.append(("profile", profile_extractor_node(state, agents)))

    if not tasks:
        logger.warning("[Node] Parallel Analysis: 无文本可分析")
        return {}

    # 并行执行
    results = await asyncio.gather(
        *[task for _, task in tasks],
        return_exceptions=True,
    )

    # 合并结果
    merged = {}
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"[Node] Parallel Analysis ({name}) 失败: {result}")
            # 设置错误状态，避免后续节点依赖失败的数据
            if name == "jd":
                merged["jd_analysis"] = {"_error": str(result), "summary": "分析失败"}
            else:
                merged["profile"] = {"_error": str(result), "name": "", "skills": []}
        elif isinstance(result, dict):
            merged.update(result)
            logger.info(f"[Node] Parallel Analysis ({name}) 成功")

    return merged


async def parallel_render_node(state: GraphState, agents: dict) -> dict:
    """并行执行 HTML Renderer 和 Interview Q&A。

    两个节点没有互相依赖：
    - html_renderer 依赖 resume_content
    - interview_qa 依赖 jd_analysis, profile, gap_analysis
    因此可以安全地并行执行。
    """
    logger.info("[Node] Parallel Render (HTML + Interview)")

    tasks = []

    # HTML Renderer
    if state.get("resume_content") and not state.get("render_config"):
        tasks.append(("html", html_renderer_node(state, agents)))

    # Interview Q&A
    if state.get("jd_analysis") and state.get("profile") and state.get("gap_analysis"):
        tasks.append(("interview", interview_qa_node(state, agents)))

    if not tasks:
        logger.warning("[Node] Parallel Render: 无任务可执行")
        return {}

    # 并行执行
    results = await asyncio.gather(
        *[task for _, task in tasks],
        return_exceptions=True,
    )

    # 合并结果
    merged = {}
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"[Node] Parallel Render ({name}) 失败: {result}")
        elif isinstance(result, dict):
            merged.update(result)
            logger.info(f"[Node] Parallel Render ({name}) 成功")

    return merged


async def clarifier_node(state: GraphState, agents: dict) -> dict:
    """Clarifier 节点：智能检测缺失信息，生成澄清问题。

    支持多轮对话：
    - 如果有 clarification_history，说明是多轮澄清
    - 解析用户回复，提取提供的信息
    - 当信息齐全时返回 ready_to_proceed=True
    """
    logger.info("[Node] Clarifier")
    agent = agents["clarifier"]

    # 判断是否多轮澄清
    clarification_history = state.get("clarification_history", [])
    is_multi_turn = len(clarification_history) > 0

    result = await agent.run(
        user_message=state.get("user_message", ""),
        session_state=_build_session_state(state),
        route_reason=state.get("route_reason", ""),
        is_multi_turn=is_multi_turn,
        # 注入最近对话历史（排除当前消息，当前消息由 user_message 单独携带）
        conversation_history=(state.get("messages") or [])[:-1],
    )

    # 构建更新
    updates: dict = {}

    if result.get("ready_to_proceed"):
        # 澄清完成，可以继续处理
        updates["ready_to_proceed"] = True
        # 如果检测到需要分析 JD 或提取简历，设置路由
        if result.get("next_action"):
            updates["route"] = result["next_action"]
        # 提取的内容写入 user_message 供下游使用
        if result.get("extracted_content"):
            updates["user_message"] = result["extracted_content"]
    else:
        # 还需要继续澄清
        updates["clarification_question"] = result.get("question", "请提供更多信息以便继续处理。")

        # 记录澄清历史：
        # 1. 多轮澄清时，先把用户本次回答挂到上一轮问题上（answer 字段），
        #    否则 Clarifier 的多轮 prompt 读 item.get("answer") 永远为空
        # 2. 再追加本轮新问题
        history = list(clarification_history)
        if is_multi_turn and history:
            history[-1] = {
                **history[-1],
                "answer": state.get("user_message", ""),
            }
        new_entry = {
            "question": result.get("question", ""),
            "detected_intent": result.get("detected_intent", ""),
        }
        updates["clarification_history"] = history + [new_entry]

    return updates


def _build_session_state(state: GraphState) -> dict:
    """从 GraphState 构建会话摘要，供 Planner 使用。"""
    return {
        "has_jd": bool(state.get("jd_analysis")),
        "has_profile": bool(state.get("profile")),
        "has_gap_analysis": bool(state.get("gap_analysis")),
        "has_resume_content": bool(state.get("resume_content")),
        "has_render_config": bool(state.get("render_config")),
        "has_interview_questions": bool(state.get("interview_questions")),
        "has_jd_text": bool(state.get("jd_text")),
        "has_resume_text": bool(state.get("resume_text")),
        "content_iterations": state.get("content_iterations", 0),
        "clarification_history": state.get("clarification_history", []),
        "ready_to_proceed": state.get("ready_to_proceed", False),
    }
