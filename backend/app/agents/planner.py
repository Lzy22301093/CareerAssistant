"""Planner Agent — 路由决策（已弃用，保留用于向后兼容）。

注意：此 Agent 已被规则引擎替代，不再使用 LLM 调用。
规则引擎实现在 app/graph/edges.py 的 rule_based_route() 函数中。
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.llm import Message, Role

ROUTES = [
    "jd_analyzer",
    "profile_extractor",
    "gap_analyzer",
    "content_generator",
    "html_renderer",
    "interview_qa",
    "clarify",
]

SYSTEM_PROMPT_TEMPLATE = """你是一个智能助手的路由模块。你的任务是分析用户消息和当前会话状态，决定下一步应该调用哪个处理模块。

可用路由：
- jd_analyzer: 需要分析职位描述（JD）。触发条件：has_jd_text=true（有解析后的JD文件）且 has_jd=false（尚未分析）
- profile_extractor: 需要提取简历画像。触发条件：has_resume_text=true（有解析后的简历文件）且 has_profile=false（尚未提取）
- gap_analyzer: 已有 JD 分析和候选人画像，需要对比分析匹配度（注意：必须同时有 jd_analysis 和 profile 才能选择此路由）
- content_generator: 已有差距分析，需要生成简历内容
- html_renderer: 已有简历内容，需要渲染为 HTML
- interview_qa: 用户需要面试题准备
- clarify: 需要向用户询问更多信息，或正在多轮澄清中

当前会话状态：
<<<STATE>>>

路由决策规则（按优先级）：
1. 如果 clarification_history 不为空且 ready_to_proceed=false，选择 clarify
2. 如果 has_jd_text=true 且 has_jd=false，选择 jd_analyzer（有JD文件待分析）
3. 如果 has_resume_text=true 且 has_profile=false，选择 profile_extractor（有简历文件待提取）
4. 如果用户消息包含明显的JD文本（职位要求、岗位职责等）且 has_jd=false，选择 jd_analyzer
5. 如果用户消息包含明显的简历信息（工作经历、教育背景等）且 has_profile=false，选择 profile_extractor
6. 如果 has_jd=true 但 has_profile=false，选择 profile_extractor（需要提取简历画像）
7. 如果 has_jd=false 但 has_profile=true，选择 jd_analyzer（需要分析 JD）
8. 如果 has_jd=true 且 has_profile=true 但 has_gap_analysis=false，选择 gap_analyzer
9. 如果 has_gap_analysis=true 但 has_resume_content=false，选择 content_generator
10. 如果 has_resume_content=true 但 has_render_config=false，选择 html_renderer
11. 如果 has_render_config=true 但 has_interview_questions=false，选择 interview_qa
12. 如果所有数据都齐全，选择 clarify 询问用户是否需要调整

请以 JSON 格式返回路由决策：
{
    "route": "路由名称",
    "reason": "选择该路由的简要原因"
}

注意：
1. 严格按上述规则判断，不要跳过步骤
2. gap_analyzer 必须同时有 jd_analysis 和 profile 才能选择
3. 优先检查 has_jd_text 和 has_resume_text，这是文件解析后的实际内容
4. 只返回 JSON，不要添加额外说明"""


class PlannerAgent(BaseAgent):
    """路由 Agent，分析用户意图并决定下一步调用哪个 Agent。"""

    name = "planner"
    description = "分析用户意图，路由到合适的 Agent"

    def build_messages(self, **kwargs) -> list[Message]:
        user_message = kwargs.get("user_message", "")
        session_state = kwargs.get("session_state", {})

        state_str = ""
        if isinstance(session_state, dict):
            import json
            state_str = json.dumps(session_state, ensure_ascii=False, indent=2)
        else:
            state_str = str(session_state)

        system_content = SYSTEM_PROMPT_TEMPLATE.replace("<<<STATE>>>", state_str)

        return [
            Message(role=Role.SYSTEM, content=system_content),
            Message(role=Role.USER, content=user_message),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "route" in result:
            # 验证路由是否合法
            route = result["route"]
            if route in ROUTES:
                return result
            # 路由名称不合法，尝试模糊匹配
            for valid_route in ROUTES:
                if valid_route in route:
                    result["route"] = valid_route
                    return result
        return {
            "route": "clarify",
            "reason": "无法解析路由决策，默认请求澄清",
            "_raw": content,
            "_parse_error": True,
        }
