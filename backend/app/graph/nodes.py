"""节点函数 — 每个节点调用对应的 Agent。

节点函数签名：(state: GraphState, agents: dict) -> dict（返回要更新的字段）

v4 简化：删除 clarifier 节点，planner 直接按查表路由。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

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


async def planner_node(state: GraphState, agents: dict) -> dict:
    """Planner 节点（v4）：LLM 意图分类 + 查表路由。

    参考项目模式：classify_intent → build_execution_plan → 取第一个节点。
    """
    logger.info("[Node] Planner (Intent + Plan)")
    from app.graph.edges import build_execution_plan
    from app.graph.intent import classify_intent

    # 0. 基于上传文件的规则预判：文件刚上传时，LLM 意图分类可能不准
    #    （用户消息可能是"帮我分析"之类的模糊指令，LLM 会误判为 gap_analysis）
    intent = None
    uploaded_files = state.get("uploaded_files", [])
    if uploaded_files:
        has_jd_text = bool(state.get("jd_text"))
        has_resume_text = bool(state.get("resume_text"))
        has_jd_analysis = _has_valid_data(state.get("jd_analysis"))
        has_profile = _has_valid_data(state.get("profile"))
        # 有 JD 文本但尚未分析 → upload_jd
        if has_jd_text and not has_jd_analysis:
            intent = "upload_jd"
            logger.info("[Planner] 规则预判：有 JD 文本未分析 → upload_jd")
        # 有简历文本但尚未提取画像 → upload_profile
        elif has_resume_text and not has_profile:
            intent = "upload_profile"
            logger.info("[Planner] 规则预判：有简历文本未提取 → upload_profile")

    # 1. LLM 意图分类（规则未命中时）
    if intent is None:
        llm = agents["planner"].llm
        intent_result = await classify_intent(llm, state.get("user_message", ""), state)
        intent = intent_result["intent"]
    else:
        intent_result = {"intent": intent, "reason": "规则预判（文件上传）", "confidence": 1.0}

    # 1.5. 消息即文件兜底：用户直接粘贴 JD/简历文本到聊天框（未上传文件）时，
    #       intent 已被 LLM 识别为 upload_jd/upload_profile，但 jd_text/resume_text 为空。
    #       将消息内容作为对应文本，使下游节点有输入可处理。
    extra_returns: dict[str, Any] = {}
    user_msg = state.get("user_message", "")
    if intent == "upload_jd" and not state.get("jd_text") and len(user_msg) > 50:
        logger.info("[Planner] 消息即 JD：jd_text 为空，将用户消息作为 JD 文本（%d 字符）", len(user_msg))
        extra_returns["jd_text"] = user_msg
    if intent == "upload_profile" and not state.get("resume_text") and len(user_msg) > 50:
        logger.info("[Planner] 消息即简历：resume_text 为空，将用户消息作为简历文本（%d 字符）", len(user_msg))
        extra_returns["resume_text"] = user_msg

    # 2. 求职信场景：从消息推断渠道
    channel = None
    if intent == "generate_cover_letter":
        msg = (state.get("user_message") or "").lower()
        if any(k in msg for k in ("打招呼", "问候", "linkedin", "私信", "消息")):
            channel = "linkedin_message"
        elif any(k in msg for k in ("求职信", "邮件", "cover letter", "正式", "email")):
            channel = "email"

    # 3. 构建执行计划（查表 + 状态截断）
    #    extra_returns 中的文本需要同步到 state 供 build_execution_plan 检查
    state_with_intent = dict(state)
    state_with_intent.update(extra_returns)
    state_with_intent["intent"] = intent
    if channel:
        state_with_intent["cover_letter_channel"] = channel
    plan = build_execution_plan(intent, state_with_intent)

    # 4. 计划为空 → 直接结束（export 等意图）
    if not plan:
        logger.info(f"[Node] Planner: intent={intent}, plan 为空 → END")
        return {
            "intent": intent,
            "intent_reason": intent_result.get("reason", ""),
            "execution_plan": [],
            "route": "end",
            "route_reason": f"意图={intent}，无需执行节点",
            "workflow_trace": [
                trace_item(
                    "planner", "success",
                    input_summary=f"用户输入：{state.get('user_message', '')[:120]}",
                    output_summary=f"意图={intent} → 计划为空（END）",
                    artifacts={"intent": intent, "reason": intent_result.get("reason", ""), "plan": []},
                )
            ],
            **extra_returns,
        }

    # 5. 设置执行计划，plan_advance 节点会逐个弹出并路由
    next_node = plan[0]
    logger.info(f"[Node] Planner: intent={intent}, plan={plan}, next={next_node}")

    return {
        "intent": intent,
        "intent_reason": intent_result.get("reason", ""),
        "cover_letter_channel": channel or state.get("cover_letter_channel", ""),
        "execution_plan": plan,
        "route": next_node,
        "route_reason": f"意图={intent}，计划={plan}",
        "workflow_trace": [
            trace_item(
                "planner", "success",
                input_summary=f"用户输入：{state.get('user_message', '')[:120]}",
                output_summary=f"意图={intent} → 计划={plan}",
                artifacts={"intent": intent, "reason": intent_result.get("reason", ""), "plan": plan},
            )
        ],
        **extra_returns,
    }


@traced("jd_analyzer", input_summary="分析职位描述")
async def jd_analyzer_node(state: GraphState, agents: dict) -> dict:
    """JD Analyzer 节点：分析职位描述。"""
    logger.info("[Node] JD Analyzer")
    agent = agents["jd_analyzer"]

    jd_text = state.get("jd_text", "")

    if not jd_text:
        uploaded_files = state.get("uploaded_files", [])
        if uploaded_files:
            logger.error(f"[Node] JD Analyzer: 有 {len(uploaded_files)} 个上传文件，但 JD 文本为空！")
            return {"jd_analysis": {
                "_error": "file_parse_failed",
                "summary": "文件解析失败，请确认文件格式是否正确",
                "_hint": "请尝试：1) 复制 JD 文本直接粘贴 2) 使用文字型 PDF 3) 检查文件是否损坏"
            }}
        else:
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

    if len(jd_text) < 50:
        logger.warning(f"[Node] JD Analyzer: JD 文本过短 ({len(jd_text)} 字符)")

    logger.info(f"[Node] JD Analyzer: 使用 JD 文本 ({len(jd_text)} 字符)")
    result = await agent.run(jd_text=jd_text)
    return {
        "jd_analysis": result,
        "jd_analyzed_version": state.get("jd_input_version", 0),
    }


@traced("profile_extractor", input_summary="提取简历画像")
async def profile_extractor_node(state: GraphState, agents: dict) -> dict:
    """Profile Extractor 节点：从简历提取候选人画像。"""
    logger.info("[Node] Profile Extractor")
    agent = agents["profile_extractor"]

    resume_text = state.get("resume_text", "")

    if not resume_text:
        uploaded_files = state.get("uploaded_files", [])
        if uploaded_files:
            logger.error(f"[Node] Profile Extractor: 有 {len(uploaded_files)} 个上传文件，但简历文本为空！")
            return {"profile": {
                "_error": "file_parse_failed",
                "name": "",
                "skills": [],
                "experience": [],
                "projects": [],
                "education": [],
                "_hint": "文件解析失败，请确认：1) 文件是否为文字型 PDF 2) 文件是否损坏 3) 尝试重新上传"
            }}
        else:
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

    if len(resume_text) < 50:
        logger.warning(f"[Node] Profile Extractor: 简历文本过短 ({len(resume_text)} 字符)")

    logger.info(f"[Node] Profile Extractor: 使用简历文本 ({len(resume_text)} 字符)")

    existing_profile = state.get("profile") or {}
    result = await agent.run(
        resume_text=resume_text,
        existing_profile=existing_profile,
    )

    if result.get("_parse_error"):
        logger.warning("[Node] Profile Extractor: JSON 解析失败")
    elif not result.get("name") and not result.get("skills"):
        logger.warning("[Node] Profile Extractor: 解析结果缺少关键字段")

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
                "questions_to_ask": [
                    "请提供目标岗位的 JD（职位描述）",
                    "请上传您的简历或粘贴个人经历",
                ],
                "_error": "missing_inputs",
            }
        }

    agent = agents["gap_analyzer"]
    result = await agent.run(jd_analysis=jd, profile=profile)

    # 确保 questions_to_ask 字段存在
    if "questions_to_ask" not in result:
        result["questions_to_ask"] = []

    return {
        "gap_analysis": result,
        "gap_based_jd": state.get("jd_input_version", 0),
        "gap_based_profile": state.get("profile_input_version", 0),
    }


@traced("content_generator", input_summary="生成简历内容")
async def content_generator_node(state: GraphState, agents: dict) -> dict:
    """Content Generator 节点：生成简历内容。

    防护：没有 profile 和 jd_analysis 时跳过，不编造数据。
    """
    logger.info("[Node] Content Generator")

    # 防编造检查
    if not _has_valid_data(state.get("profile")) or not _has_valid_data(state.get("jd_analysis")):
        logger.warning("[Node] Content Generator skipped: 缺少 profile 或 jd_analysis")
        return {
            "resume_content": {},
            "workflow_trace": [trace_item(
                "content_generator", "skipped",
                output_summary="缺少简历画像或 JD 分析，跳过内容生成",
            )],
        }

    agent = agents["content_generator"]

    user_instructions = ""
    if state.get("intent") == "content_edit":
        user_instructions = state.get("user_message", "")

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
    """Interview Q&A 节点：生成面试题。

    降级策略：至少有 JD 或 profile 之一即可尝试生成，
    缺少的数据传空 dict，由 Agent prompt 处理信息不足的情况。
    """
    logger.info("[Node] Interview Q&A")

    jd = state.get("jd_analysis")
    profile = state.get("profile")
    gap = state.get("gap_analysis")

    # 至少需要 JD 或 profile 之一，否则完全无输入无法生成
    if not _has_valid_data(jd) and not _has_valid_data(profile):
        logger.warning("[Node] Interview Q&A skipped: JD 和 profile 均为空")
        return {
            "interview_questions": {"questions": []},
            "workflow_trace": [trace_item(
                "interview_qa", "skipped",
                output_summary="缺少 JD 和简历数据，跳过面试题生成",
            )],
        }

    # 降级日志：哪些数据缺失
    if not _has_valid_data(jd):
        logger.warning("[Node] Interview Q&A: JD 数据缺失，将基于 profile 生成")
    if not _has_valid_data(profile):
        logger.warning("[Node] Interview Q&A: Profile 数据缺失，将基于 JD 生成")
    if not _has_valid_data(gap):
        logger.info("[Node] Interview Q&A: 差距分析缺失，跳过 gap 上下文")

    agent = agents["interview_qa"]
    result = await agent.run(
        jd_analysis=jd if _has_valid_data(jd) else {},
        profile=profile if _has_valid_data(profile) else {},
        gap_analysis=gap if _has_valid_data(gap) else {},
        user_instructions="",
    )
    iterations = state.get("interview_iterations", 0) + 1
    return {
        "interview_questions": result,
        "interview_iterations": iterations,
        "interview_based_jd": state.get("jd_input_version", 0),
        "interview_based_profile": state.get("profile_input_version", 0),
    }


async def plan_advance_node(state: GraphState, agents: dict) -> dict:
    """计划推进节点：从 execution_plan 取出下一个待执行节点。

    这是线性流水线的核心：每个业务节点执行完后经过此节点，
    取出下一个待执行节点名，通过 route 字段传递给条件边路由。
    """
    plan = list(state.get("execution_plan", []))
    if plan:
        next_node = plan.pop(0)
        logger.info(f"[Node] plan_advance: 取出 {next_node}，剩余 {plan}")
        return {"execution_plan": plan, "route": next_node}
    else:
        logger.info("[Node] plan_advance: plan 已空 → END")
        return {"execution_plan": [], "route": "__end__"}


@traced("question", input_summary="基于状态自由问答")
async def question_node(state: GraphState, agents: dict) -> dict:
    """Question 节点（v3）：基于当前会话状态自由回答。"""
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


@traced("clarifier", input_summary="面试记录追问")
async def clarifier_node(state: GraphState, agents: dict) -> dict:
    """Clarifier 节点（v4 简化版）：仅处理面试记录的多轮追问。

    record_interview 意图需要多轮对话收集面试信息（公司/岗位/结果/问题/失分点），
    其他意图不再经过此节点。
    """
    logger.info("[Node] Clarifier (interview record)")
    from app.services.interview_memory import InterviewMemoryService

    svc = InterviewMemoryService()
    draft = dict(state.get("interview_draft") or {})
    is_multi_turn = bool(draft)

    if is_multi_turn:
        # 多轮：LLM 解析用户回复 → 合并进 interview_draft
        llm = agents["planner"].llm  # 复用 planner 的 LLM
        draft = await svc.parse_interview_reply(llm, state.get("user_message", ""), draft)
    else:
        # 首轮：用 LLM 从用户消息提取初始信息
        llm = agents["planner"].llm
        draft = await svc.parse_interview_reply(llm, state.get("user_message", ""), draft)

    if svc.is_complete(draft):
        logger.info("[Node] Interview Record: 信息齐全，等待入库")
        return {
            "interview_draft": draft,
            "execution_plan": [],  # 清空计划 → END
            "workflow_trace": [
                trace_item("clarifier", "success",
                           input_summary="面试记录",
                           output_summary=f"已收集 {draft.get('company', '')} {draft.get('job_title', '')} {draft.get('result', '')}")
            ],
        }

    question = svc.next_question(draft) or "还有需要补充的信息吗？"
    logger.info(f"[Node] Interview Record: 追问 -> {question}")
    return {
        "interview_draft": draft,
        "answer": question,  # 通过 answer 字段返回追问问题
        "execution_plan": [],  # 清空计划 → END（等待用户回复）
        "workflow_trace": [
            trace_item("clarifier", "success",
                       input_summary="面试记录追问",
                       output_summary=question)
        ],
    }


async def interview_sim_node(state: GraphState, agents: dict) -> dict:
    """模拟面试入口：标记意图，由 sessions.py 拦截处理。"""
    logger.info("[Node] Interview Sim → 标记意图")
    return {"intent": "interview_sim", "execution_plan": []}
