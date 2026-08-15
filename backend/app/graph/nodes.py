"""节点函数 — 每个节点调用对应的 Agent。

节点函数签名：(state: GraphState) -> dict（返回要更新的字段）
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.graph.reflection import PASS_SCORE
from app.graph.state import GraphState
from app.graph.trace import traced, trace_item

logger = logging.getLogger(__name__)


def _has_valid_data(data: Any) -> bool:
    """检查数据是否为有效的非空字典（排除错误状态）。"""
    if not isinstance(data, dict):
        return bool(data)
    if data.get("_error"):
        return False
    return bool(data)


def _infer_channel(user_message: str) -> str | None:
    """从用户消息推断求职信渠道（v3）。"""
    if not user_message:
        return None
    msg = user_message.lower()
    if any(k in msg for k in ("打招呼", "问候", "linkedin", "私信", "消息")):
        return "linkedin_message"
    if any(k in msg for k in ("求职信", "邮件", "cover letter", "正式", "email")):
        return "email"
    return None


async def planner_node(state: GraphState, agents: dict) -> dict:
    """Planner 节点（v3）：LLM 意图分类 + 规则引擎兜底（guardrail）。"""
    logger.info("[Node] Planner (Intent + Rule guardrail)")
    from app.graph.edges import rule_based_route
    from app.graph.intent import classify_intent

    # 1. LLM 意图分类（失败/低置信 → fallback，由规则引擎兜底）
    llm = agents["planner"].llm
    intent_result = await classify_intent(llm, state.get("user_message", ""), state)
    intent = intent_result["intent"]

    # 2. 求职信场景：从消息推断渠道（"先让用户选"的规则部分）
    channel = _infer_channel(state.get("user_message", "")) if intent == "generate_cover_letter" else None

    # 3. 路由决策（意图优先，规则引擎执行）
    state_with_intent = dict(state)
    state_with_intent["intent"] = intent
    if channel:
        state_with_intent["cover_letter_channel"] = channel
    route = rule_based_route(state_with_intent)

    plan = [route] if route != "end" else []
    logger.info(f"[Node] Planner: intent={intent}, route={route}")

    return {
        "intent": intent,
        "intent_reason": intent_result.get("reason", ""),
        "cover_letter_channel": channel or state.get("cover_letter_channel", ""),
        "route": route,
        "route_reason": f"意图={intent}，路由={route}",
        "execution_plan": plan,
        "workflow_trace": [
            trace_item(
                "planner", "success",
                input_summary=f"用户输入：{state.get('user_message', '')[:120]}",
                output_summary=f"意图={intent} → 路由={route}",
                artifacts={"intent": intent, "reason": intent_result.get("reason", ""), "plan": plan},
            )
        ],
    }


def _rule_based_review_check(state: GraphState) -> dict | None:
    """评审规则预检（性能优化 B1）：先跑廉价规则，通过则跳过 LLM 评审。

    规则（保守，避免误放行低质量内容）：
    1. resume_content 的 sections 非空
    2. 至少一个板块包含量化数字（如 "提升 30%"）
    3. JD 关键词在简历文本中覆盖率 >= 30%（取前 10 个关键词）

    全部满足才返回预检通过的 review_result（分数 = PASS_SCORE），
    否则返回 None 走 LLM 评审。
    """
    from app.graph.reflection import PASS_SCORE

    content = state.get("resume_content", {})
    sections = content.get("sections", [])
    if not isinstance(sections, list) or not sections:
        return None

    # 规则 2：量化数字
    has_quant = any(
        re.search(r"\d", str(sec.get("content", "")))
        for sec in sections
        if isinstance(sec, dict) and sec.get("content")
    )
    if not has_quant:
        return None

    # 规则 3：JD 关键词覆盖
    keywords = (state.get("jd_analysis") or {}).get("keywords", []) or []
    keywords = [str(k).strip().lower() for k in keywords if str(k).strip()][:10]
    if keywords:
        text = json.dumps(content, ensure_ascii=False).lower()
        matched = sum(1 for kw in keywords if kw and kw in text)
        if matched / len(keywords) < 0.3:
            return None

    return {
        "score": PASS_SCORE,
        "dimensions": {},
        "issues": [],
        "suggestions": [],
        "summary": "规则预检通过（板块完整、含量化数据、关键词覆盖达标）",
        "rule_passed": True,
    }


@traced("jd_analyzer", input_summary="分析职位描述")
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
    return {
        "jd_analysis": result,
        "jd_analyzed_version": state.get("jd_input_version", 0),
    }


@traced("profile_extractor", input_summary="提取简历画像")
async def profile_extractor_node(state: GraphState, agents: dict) -> dict:
    """Profile Extractor 节点：从简历提取候选人画像（支持增量合并）。"""
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

    # 增量合并：把已有画像传给 Agent，新材料合并进旧画像（v3）
    existing_profile = state.get("profile") or {}
    result = await agent.run(
        resume_text=resume_text,
        existing_profile=existing_profile,
    )

    # 检查解析结果质量
    if result.get("_parse_error"):
        logger.warning(f"[Node] Profile Extractor: JSON 解析失败，返回原始内容")
    elif not result.get("name") and not result.get("skills"):
        logger.warning(f"[Node] Profile Extractor: 解析结果缺少关键字段 (name, skills)")

    return {
        "profile": result,
        "profile_analyzed_version": state.get("profile_input_version", 0),
    }


@traced("gap_analyzer", input_summary="对比 JD 与画像")
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
    return {
        "gap_analysis": result,
        "gap_based_jd": state.get("jd_input_version", 0),
        "gap_based_profile": state.get("profile_input_version", 0),
    }


@traced("content_generator", input_summary="生成简历内容")
async def content_generator_node(state: GraphState, agents: dict) -> dict:
    """Content Generator 节点：生成简历内容。如果是迭代，附带评审改进建议。"""
    logger.info("[Node] Content Generator")
    agent = agents["content_generator"]

    # 检查是否有评审反馈需要改进
    review_result = state.get("review_result", {})
    user_instructions = ""
    if state.get("intent") == "content_edit":
        # content_edit 意图：用户消息即修改指令（v3）
        user_instructions = state.get("user_message", "")
    elif review_result and review_result.get("suggestions"):
        from app.graph.reflection import build_reflection_prompt
        user_instructions = build_reflection_prompt(review_result)

    result = await agent.run(
        profile=state.get("profile", {}),
        jd_analysis=state.get("jd_analysis", {}),
        gap_analysis=state.get("gap_analysis", {}),
        user_instructions=user_instructions,
    )
    iterations = state.get("content_iterations", 0) + 1
    return {
        "resume_content": result,
        "content_iterations": iterations,
        "content_based_jd": state.get("jd_input_version", 0),
        "content_based_profile": state.get("profile_input_version", 0),
    }


@traced("reviewer", input_summary="评审简历内容质量")
async def reviewer_node(state: GraphState, agents: dict) -> dict:
    """Reviewer 节点：评审简历内容质量。

    性能优化 B1：先跑规则预检，通过则直接返回 review_result，
    跳过一次 LLM 评审调用（评审是高频调用且规则可覆盖常见合格场景）。
    """
    # 规则预检
    pre_check = _rule_based_review_check(state)
    if pre_check is not None:
        logger.info("[Node] Reviewer: 规则预检通过，跳过 LLM 评审")
        return {"review_result": pre_check}

    logger.info("[Node] Reviewer (LLM)")
    agent = agents["reviewer"]
    result = await agent.run(
        resume_content=state.get("resume_content", {}),
        jd_analysis=state.get("jd_analysis", {}),
        profile=state.get("profile", {}),
    )
    return {"review_result": result}


@traced("html_renderer", input_summary="生成渲染配置")
async def html_renderer_node(state: GraphState, agents: dict) -> dict:
    """HTML Renderer 节点：生成渲染配置。"""
    logger.info("[Node] HTML Renderer")
    agent = agents["html_renderer"]
    result = await agent.run(
        resume_content=state.get("resume_content", {}),
    )
    return {"render_config": result}


@traced("interview_qa", input_summary="生成面试题")
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
    return {
        "interview_questions": result,
        "interview_iterations": iterations,
        "interview_based_jd": state.get("jd_input_version", 0),
        "interview_based_profile": state.get("profile_input_version", 0),
    }


@traced("interview_reviewer", input_summary="评审面试题质量")
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
            _merge_with_trace(merged, result)
            logger.info(f"[Node] Parallel Analysis ({name}) 成功")

    return merged


async def parallel_post_node(state: GraphState, agents: dict) -> dict:
    """简历生成后的并行阶段：简历评审 ∥ 面试题生成（性能优化 B2）。

    两个任务没有互相依赖：
    - reviewer 依赖 resume_content
    - interview_qa 依赖 jd_analysis, profile, gap_analysis（不依赖简历内容）
    因此可以并行执行，把 interview_qa 从串行链路中提前，节省一个时间段。

    注意：reviewer 内部先跑规则预检，通过则跳过 LLM 调用。
    """
    logger.info("[Node] Parallel Post (Review + Interview)")

    tasks = []

    # 简历评审（可能被规则预检短路，无 LLM 调用）
    tasks.append(("review", reviewer_node(state, agents)))

    # 面试题生成：仅在尚未生成且前置数据齐全时执行
    has_interview = _has_valid_data(state.get("interview_questions"))
    if (
        not has_interview
        and state.get("jd_analysis")
        and state.get("profile")
        and state.get("gap_analysis")
    ):
        tasks.append(("interview", interview_qa_node(state, agents)))

    # 并行执行
    results = await asyncio.gather(
        *[task for _, task in tasks],
        return_exceptions=True,
    )

    # 合并结果
    merged = {}
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"[Node] Parallel Post ({name}) 失败: {result}")
            if name == "review":
                # 评审失败不阻塞主流程：给一个高分兜底，继续渲染
                merged["review_result"] = {
                    "score": PASS_SCORE,
                    "dimensions": {},
                    "issues": [],
                    "suggestions": [],
                    "summary": "评审调用失败，按通过处理",
                    "_review_error": True,
                }
        elif isinstance(result, dict):
            _merge_with_trace(merged, result)
            logger.info(f"[Node] Parallel Post ({name}) 成功")

    return merged


def _merge_with_trace(merged: dict, result: dict) -> None:
    """合并子节点返回值，workflow_trace 用 extend 累积（避免覆盖）。"""
    trace = result.pop("workflow_trace", None)
    merged.update(result)
    if trace:
        merged.setdefault("workflow_trace", []).extend(trace)


@traced("question", input_summary="基于状态自由问答")
async def question_node(state: GraphState, agents: dict) -> dict:
    """Question 节点（v3）：基于当前会话状态自由回答，只读不写业务状态。"""
    logger.info("[Node] Question")
    agent = agents["question"]
    result = await agent.run(
        state=state,
        user_message=state.get("user_message", ""),
    )
    return {"answer": result.get("answer", "")}


@traced("cover_letter", input_summary="生成求职信/打招呼文案")
async def cover_letter_node(state: GraphState, agents: dict) -> dict:
    """Cover Letter 节点（v3）：生成求职信或招聘软件打招呼文案。"""
    logger.info("[Node] Cover Letter")
    agent = agents["cover_letter"]
    result = await agent.run(
        profile=state.get("profile", {}),
        jd_analysis=state.get("jd_analysis", {}),
        gap_analysis=state.get("gap_analysis", {}),
        channel=state.get("cover_letter_channel", "email"),
        user_instructions=state.get("user_message", ""),
    )
    result.setdefault("channel", state.get("cover_letter_channel", "email"))
    return {"cover_letter": result}


@traced("clarifier", input_summary="澄清需求")
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

    # 面试记录（M3）：多轮追问收集面试信息（公司/岗位/结果/问题/失分点）
    if state.get("intent") == "record_interview":
        return await _handle_interview_recording(state, agents, clarification_history, is_multi_turn)

    # 求职信渠道选择（v3）：意图=generate_cover_letter 且渠道未定 → 直接给选项，不调 LLM
    if state.get("intent") == "generate_cover_letter" and not state.get("cover_letter_channel"):
        logger.info("[Node] Clarifier: 求职信渠道未选，给出选项")
        question = "你想生成哪种文案？\n1. 招聘软件打招呼（简短，100 字以内）\n2. 正式求职信（邮件，150-300 字）"
        history = list(clarification_history)
        if is_multi_turn and history:
            history[-1] = {**history[-1], "answer": state.get("user_message", "")}
        history = history + [{"question": question, "detected_intent": "select_channel"}]
        return {
            "clarification_question": question,
            "clarification_history": history,
            "workflow_trace": [
                trace_item("clarifier", "success",
                           input_summary="求职信渠道选择",
                           output_summary="询问用户选择渠道")
            ],
        }

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


async def _handle_interview_recording(
    state: GraphState, agents: dict, clarification_history: list, is_multi_turn: bool
) -> dict:
    """面试记录多轮追问（M3 长久陪伴）。

    - 多轮：LLM 解析用户回复 → 合并进 interview_draft → 缺哪个字段问哪个
    - 核心字段齐全（公司/岗位/结果）→ ready_to_proceed，由 sessions.py 入库
    """
    from app.services.interview_memory import InterviewMemoryService

    svc = InterviewMemoryService()
    draft = dict(state.get("interview_draft") or {})

    if is_multi_turn:
        llm = agents["clarifier"].llm
        draft = await svc.parse_interview_reply(llm, state.get("user_message", ""), draft)

    history = list(clarification_history)
    if is_multi_turn and history:
        history[-1] = {**history[-1], "answer": state.get("user_message", "")}

    if svc.is_complete(draft):
        logger.info("[Node] Interview Record: 信息齐全，等待入库")
        return {
            "interview_draft": draft,
            "ready_to_proceed": True,
            "clarification_history": history,
            "workflow_trace": [
                trace_item("clarifier", "success",
                           input_summary="面试记录",
                           output_summary=f"已收集 {draft.get('company')} {draft.get('job_title')} {draft.get('result')}")
            ],
        }

    question = svc.next_question(draft) or "还有需要补充的信息吗？"
    logger.info(f"[Node] Interview Record: 追问 -> {question}")
    return {
        "interview_draft": draft,
        "clarification_question": question,
        "clarification_history": history + [{"question": question, "detected_intent": "interview_record"}],
        "ready_to_proceed": False,
        "workflow_trace": [
            trace_item("clarifier", "success",
                       input_summary="面试记录追问",
                       output_summary=question)
        ],
    }


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
