"""Trace（v3）— 节点执行轨迹记录与装饰器。

每个能力单元执行后记录 {node, status, input_summary, output_summary, error, latency_ms}，
供 SSE 推送与排查。参考 ai-career-copilot 的 workflow_trace。
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


def trace_item(
    node: str,
    status: str = "success",  # success / skipped / failed
    input_summary: str = "",
    output_summary: str = "",
    error: str = "",
    artifacts: dict[str, Any] | None = None,
    latency_ms: float = 0.0,
) -> dict[str, Any]:
    """构造一条 trace 记录。"""
    item: dict[str, Any] = {
        "node": node,
        "status": status,
        "input_summary": input_summary[:500],
        "output_summary": output_summary[:500],
        "latency_ms": round(latency_ms, 1),
    }
    if error:
        item["error"] = error[:500]
    if artifacts:
        item["artifacts"] = artifacts
    return item


def summarize(text: str, limit: int = 120) -> str:
    """截断摘要。"""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def traced(node_name: str, input_summary: str = ""):
    """节点装饰器：包装节点函数，自动记录成功 trace 并追加到 state 更新。

    失败时**向上抛异常**（不吞），由 LangGraph 中断整图，
    已完成的节点产物由 sessions.py 的即时持久化保住；
    并行容器（gather return_exceptions）会捕获为 Exception 单独处理。

    用法：
        @traced("jd_analyzer")
        async def jd_analyzer_node(state, agents): ...

    节点返回值 dict 会被追加 workflow_trace 字段（依赖 GraphState 的 add 语义累积）。
    """
    def decorator(fn: Callable[..., Awaitable[dict]]) -> Callable[..., Awaitable[dict]]:
        @wraps(fn)
        async def wrapper(state: dict, agents: dict) -> dict:
            start = time.perf_counter()
            result = await fn(state, agents)
            latency = (time.perf_counter() - start) * 1000
            result["workflow_trace"] = [
                trace_item(
                    node_name, "success",
                    input_summary=input_summary,
                    output_summary=_summarize_result(result),
                    latency_ms=latency,
                )
            ]
            return result
        return wrapper
    return decorator


def _summarize_result(result: dict[str, Any]) -> str:
    """从节点返回值生成简短摘要。"""
    parts = []
    if result.get("jd_analysis"):
        jd = result["jd_analysis"]
        parts.append(f"职位={jd.get('job_title', '未知')}")
    if result.get("profile"):
        profile = result["profile"]
        parts.append(f"画像 name={profile.get('name', '')}, skills={len(profile.get('skills', []))}个")
    if result.get("gap_analysis"):
        gap = result["gap_analysis"]
        parts.append(f"匹配度={gap.get('overall_score', 0)}")
    if result.get("resume_content"):
        sections = result["resume_content"].get("sections", [])
        parts.append(f"简历板块={len(sections)}个")
    if result.get("review_result"):
        review = result["review_result"]
        parts.append(f"评审分={review.get('score', 0)}")
    if result.get("render_config"):
        render = result["render_config"]
        parts.append(f"模板={render.get('template', '')}")
    if result.get("interview_questions"):
        questions = result["interview_questions"].get("questions", [])
        parts.append(f"面试题={len(questions)}道")
    if result.get("answer"):
        parts.append(f"回答={summarize(result['answer'])}")
    if result.get("cover_letter"):
        cl = result["cover_letter"]
        parts.append(f"求职信 channel={cl.get('channel', '')}, {summarize(cl.get('body', ''))}")
    if not parts:
        keys = [k for k in result.keys() if k != "workflow_trace"]
        parts.append(f"更新字段: {', '.join(keys[:5])}")
    return "；".join(parts)
