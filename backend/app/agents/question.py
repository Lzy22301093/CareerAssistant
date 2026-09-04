"""Question Agent（v3）— 基于当前会话状态自由回答用户问题，只读不改。

用户问"这岗位我匹配吗 / 简历里有什么 / 刚才生成了哪些面试题"时，
基于 GraphState 摘要回答。信息不足时明确告知缺什么。
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个职业助手问答专家。你可以读取工作流的当前状态变量，并用自然语言回答用户问题。

回答要求：
- 优先依据状态变量中的事实回答，不要编造状态中没有的信息
- 如果信息不足，明确说明缺少哪些数据，并给出用户下一步可以补充什么
- 用户询问岗位、候选人、简历、差距、渲染配置、面试题时，都可以从状态变量中综合回答
- 回答要直接、自然，使用中文"""


def _compact_state_context(state: dict) -> dict:
    """构造问答模型可见的状态快照，排除大字段与内部字段。"""
    exclude = {
        "user_message", "messages", "workflow_trace", "execution_plan",
        "route", "route_reason", "intent", "intent_reason", "clarification_history",
        "ready_to_proceed", "uploaded_files", "session_id",
    }
    ctx = {k: v for k, v in state.items() if k not in exclude}

    # 压缩 resume_content 的 raw_text（可能很大）
    rc = ctx.get("resume_content") or {}
    if isinstance(rc, dict) and rc.get("raw_text"):
        rc = dict(rc)
        rc["raw_text"] = (rc["raw_text"] or "")[:2000]
        ctx["resume_content"] = rc

    return ctx


class QuestionAgent(BaseAgent):
    """基于当前会话状态回答用户问题（只读）。"""

    name = "question"
    description = "基于当前会话状态自由问答"

    temperature = 0.3
    # max_tokens 需足够大：MIMO 模型可能有内部思考链消耗 token，过小会导致输出为空
    max_tokens = 4096

    def build_messages(self, **kwargs) -> list[Message]:
        state = kwargs.get("state", {})
        user_message = kwargs.get("user_message", "")

        state_json = json.dumps(
            _compact_state_context(state), ensure_ascii=False, indent=2
        )
        user_content = (
            f"用户问题：\n{user_message}\n\n"
            f"当前 graph state JSON：\n{state_json}"
        )
        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        answer = content.strip()
        if not answer:
            answer = "我暂时没有从当前状态中找到可回答的信息。可以补充岗位、个人材料或先生成简历后再问我。"
        return {"answer": answer}
