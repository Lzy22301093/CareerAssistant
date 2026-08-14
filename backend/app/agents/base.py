"""Agent 基类定义。

所有 Agent 继承 BaseAgent，实现 build_messages() 和 parse_response() 两个抽象方法。
run() 方法编排：构造消息 → 调用 LLM → （工具调用循环）→ 解析响应。

工具调用循环（P1-5 新增）：
1. 首次调用 LLM 时携带该 Agent 注册的 tools（function calling）
2. 若响应包含 tool_calls，逐个执行工具，把结果以 tool 角色消息回填
3. 继续调用 LLM，直到返回纯文本内容（或达到最大轮数）
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from app.llm import LLMProvider, Message, Response, Role, ToolCall, ToolDefinition
from app.llm.retry import is_retryable_llm_error, with_retry
from app.tools.base import Tool

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 120  # 单 Agent 超时 120s（MIMO API 响应较慢）
TOOL_LOOP_MAX_ITERATIONS = 5  # 单次 run() 内最大 tool-calling 轮数


class BaseAgent(ABC):
    """Agent 基类，封装 LLM 调用、超时控制和工具调用循环。

    子类必须实现：
    - build_messages(**kwargs) -> list[Message]
    - parse_response(content: str) -> dict

    可选：
    - 设置类属性 tools: list[Tool]，则该 Agent 具备 function-calling 能力。
    """

    name: str = ""
    description: str = ""
    tools: list[Tool] = []

    def __init__(self, llm: LLMProvider, tools: list[Tool] | None = None):
        self.llm = llm
        if tools is not None:
            self.tools = list(tools)

    @abstractmethod
    def build_messages(self, **kwargs) -> list[Message]:
        """构造 LLM 消息列表。子类必须实现。"""
        ...

    @abstractmethod
    def parse_response(self, content: str) -> dict:
        """解析 LLM 响应为结构化数据。子类必须实现。"""
        ...

    # --- 工具调用支持 ---

    def _tool_definitions(self) -> list[ToolDefinition]:
        """把注册的工具转换为 LLM function-calling 定义。"""
        return [
            ToolDefinition(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in self.tools
        ]

    def _find_tool(self, name: str) -> Tool | None:
        for t in self.tools:
            if t.name == name:
                return t
        return None

    async def _execute_tool(self, tool_call: ToolCall) -> str:
        """执行单个工具调用，返回序列化后的结果（供 tool 角色消息使用）。

        任何失败都不会抛出异常，而是把错误信息返回给 LLM 自行处理。
        """
        tool = self._find_tool(tool_call.name)
        if tool is None:
            logger.warning(f"[{self.name}] 未知工具: {tool_call.name}")
            return json.dumps({"error": f"未知工具: {tool_call.name}"}, ensure_ascii=False)

        try:
            args = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError as e:
            logger.warning(f"[{self.name}] 工具参数解析失败: {e}")
            args = {}

        try:
            result = await tool.execute(**args)
        except Exception as e:
            logger.error(f"[{self.name}] 工具 {tool_call.name} 执行异常: {e}", exc_info=True)
            return json.dumps({"error": f"工具执行异常: {e}"}, ensure_ascii=False)

        if result.success:
            return json.dumps({"result": result.data}, ensure_ascii=False)
        return json.dumps({"error": result.error or "工具执行失败"}, ensure_ascii=False)

    # --- LLM 调用 ---

    @with_retry(max_retries=3, base_delay=1.0, retryable=is_retryable_llm_error)
    async def _call_llm(self, messages: list[Message], **kwargs) -> Response:
        """调用 LLM 并返回完整响应（含 tool_calls），带错误类型感知的重试。"""
        return await self.llm.chat(messages, **kwargs)

    async def run(self, **kwargs) -> dict:
        """执行 Agent：构造消息 → 工具调用循环 → 解析响应。

        工具调用循环：
        - 若 LLM 返回 tool_calls，执行工具并把结果回填，继续调用
        - 直到 LLM 返回纯文本，或达到 TOOL_LOOP_MAX_ITERATIONS

        Returns:
            解析后的结构化字典。

        Raises:
            asyncio.TimeoutError: LLM 调用超时。
        """
        messages = self.build_messages(**kwargs)
        logger.info(f"[{self.name}] calling LLM with {len(messages)} message(s)")

        tool_defs = self._tool_definitions()
        response: Response | None = None

        for iteration in range(TOOL_LOOP_MAX_ITERATIONS + 1):
            response = await asyncio.wait_for(
                self._call_llm(messages, tools=tool_defs or None),
                timeout=AGENT_TIMEOUT,
            )

            # 没有工具调用 → 拿到最终内容，退出循环
            if not response.tool_calls:
                break

            if not self.tools:
                # 模型意外返回了 tool_calls 但 Agent 未注册工具：视为异常输出
                logger.warning(f"[{self.name}] LLM 返回 tool_calls 但该 Agent 未注册工具")
                break

            # 把 assistant 消息（含 tool_calls）加入对话，再追加各工具结果
            assistant_msg = Message(
                role=Role.ASSISTANT,
                content=response.content or "",
                tool_calls=list(response.tool_calls),
            )
            messages.append(assistant_msg)

            tool_results = await asyncio.gather(
                *[self._execute_tool(tc) for tc in response.tool_calls]
            )
            for tc, result_text in zip(response.tool_calls, tool_results):
                messages.append(
                    Message(role=Role.TOOL, content=result_text, tool_call_id=tc.id)
                )
            logger.info(
                f"[{self.name}] tool round {iteration + 1}: "
                f"executed {len(response.tool_calls)} tool(s)"
            )

            if iteration == TOOL_LOOP_MAX_ITERATIONS - 1:
                logger.warning(f"[{self.name}] 达到工具调用最大轮数 {TOOL_LOOP_MAX_ITERATIONS}")

        if response is None:
            raise RuntimeError(f"[{self.name}] LLM 未返回任何响应")

        return self.parse_response(response.content or "")

    # --- 通用 JSON 解析辅助方法 ---

    @staticmethod
    def extract_json(text: str) -> dict | None:
        """从 LLM 响应中提取 JSON 对象。

        处理常见格式：
        - 纯 JSON 字符串
        - ```json ... ``` 包裹的 JSON
        - 文本中嵌入的 JSON
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试提取 ```json ... ``` 代码块
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except (json.JSONDecodeError, TypeError):
                pass

        # 使用括号匹配提取最外层 JSON 对象（支持任意深度嵌套）
        def extract_balanced_json(s: str) -> str | None:
            """提取最外层的 {...} 或 [...]"""
            start = None
            depth = 0
            for i, c in enumerate(s):
                if c in ('{', '['):
                    if depth == 0:
                        start = i
                    depth += 1
                elif c in ('}', ']'):
                    depth -= 1
                    if depth == 0 and start is not None:
                        return s[start:i+1]
            return None

        json_str = extract_balanced_json(text)
        if json_str:
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                pass

        return None
