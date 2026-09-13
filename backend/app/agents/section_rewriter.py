"""SectionRewriterAgent — 简历区域改写（阶段2 指令2-2）。

生成多条候选改写；不直接覆盖原文；引入画像外数字/经历时必须自报，
服务层另有代码级数字比对兜底（见 section_rewrite_service）。
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm.base import Message, Role
from app.tools.context import compact_jd, compact_profile


class SectionRewriterAgent(BaseAgent):
    """区域改写能力单元（生成类，主模型）。"""

    name = "section_rewriter"
    temperature = 0.5
    max_tokens = 4096
    max_parse_attempts = 2  # JSON 解析失败自动回喂修复一次
    json_mode = True  # MIMO 需要 response_format=json_object，否则易返回散文导致校验失败

    SYSTEM_PROMPT = """你是资深简历改写专家。用户选中了简历中的一个区域，要求你产出改写候选。

核心规则：
1. 输出 2-3 条不同思路的候选改写，每条带 approach（一句话思路）与 changes（关键改动点列表）。
2. 只重写选中区域本身；必须基于【区域原文】与【用户画像事实】，不得凭空捏造经历。
3. 若候选引入了原文与画像中都不存在的数字（如"提升40%"、"3个月"），
   必须把这些数字逐个写入 new_numbers；若引入了新的经历/项目/证书等事实性陈述，写入 new_claims，
   并把 needs_source_confirmation 置为 true——用户将收到"需要核对来源"的提示。
4. 量化改写时优先复用原文与画像中已有的事实与数字；无法确认的内容宁可不写。
5. advice 给用户一句话建议（可为 null）。
6. 只输出 JSON 对象，格式：
{"candidates": [{"rewrite": "改写后的区域全文", "approach": "思路", "changes": ["改动点"]}],
 "needs_source_confirmation": false, "new_numbers": [], "new_claims": [], "advice": null}"""

    def build_messages(
        self,
        section_title: str = "",
        section_type: str = "custom",
        section_text: str = "",
        resume_summary: str = "",
        profile_context: dict | None = None,
        jd_analysis: dict | None = None,
        user_instruction: str = "",
        **kwargs,
    ) -> list[Message]:
        parts = [
            self.SYSTEM_PROMPT,
            "\n【选中区域】"
            f"标题：{section_title or '（无标题）'}（类型：{section_type}）\n{section_text}",
            f"\n【整份简历其它内容摘要】\n{resume_summary or '（无）'}",
            f"\n【用户画像（唯一事实来源）】\n{json.dumps(compact_profile(profile_context), ensure_ascii=False)}",
        ]
        if jd_analysis:
            parts.append(f"\n【目标岗位 JD 分析】\n{json.dumps(compact_jd(jd_analysis), ensure_ascii=False)}")
        parts.append(f"\n【用户指令】\n{user_instruction or '优化这个区域的表达与量化'}")
        return [
            Message(role=Role.SYSTEM, content="\n".join(parts)),
            Message(role=Role.USER, content="请输出改写候选 JSON。"),
        ]

    def parse_response(self, content: str) -> dict:
        parsed = self.extract_json(content)
        if parsed is None:
            return {"_parse_error": "无法从回复中提取 JSON"}
        return parsed
