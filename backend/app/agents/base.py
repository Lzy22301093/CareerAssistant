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
from app.llm.observability import start_llm_call
from app.llm.retry import is_retryable_llm_error, with_retry
from app.tools.base import Tool

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 120  # 单 Agent 超时 120s（MIMO API 响应较慢）
TOOL_LOOP_MAX_ITERATIONS = 3  # 单次 run() 内最大 tool-calling 轮数（MIMO 慢，避免超时）


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

    # 按 Agent 类型可覆盖的调用参数（性能优化 A2）：
    # - temperature: 提取类用低值保证稳定，生成类用高值保证多样性
    # - max_tokens: 提取类输出小，调小可显著降低生成耗时
    # - model: 指定使用的模型（如快速模型），None 表示用 provider 默认模型
    temperature: float = 0.7
    max_tokens: int = 4096
    model: str | None = None
    json_mode: bool = False  # 启用 response_format=json_object（MIMO/DeepSeek 支持）
    # 解析失败修复重试次数上限（>1 时，LLM 输出非 JSON 会回喂修复一次）
    max_parse_attempts: int = 1

    def __init__(
        self,
        llm: LLMProvider,
        tools: list[Tool] | None = None,
        model: str | None = None,
    ):
        self.llm = llm
        if tools is not None:
            self.tools = list(tools)
        if model is not None:
            self.model = model

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

    async def _call_llm(self, messages: list[Message], **kwargs) -> Response:
        """调用 LLM 并返回完整响应（含 tool_calls），带错误类型感知的重试。

        同时做调用级埋点（C1）：延迟 / token / 重试次数 / 错误分类，
        捕获开启时随请求汇总（见 app.llm.observability），未开启时仅打日志。
        重试在内部闭包上包 with_retry（而非装饰本方法），
        以便把 tracker 的 note_retry 作为 on_retry 回调传入。
        """
        tracker = start_llm_call(
            agent=self.name or type(self).__name__,
            model=kwargs.get("model") or getattr(self.llm, "model", "") or "",
            prompt_chars=sum(len(m.content or "") for m in messages),
        )

        async def _invoke() -> Response:
            # json_mode 仅在无工具调用时启用（function calling 与 json_object 互斥）
            if kwargs.get("json_mode") and kwargs.get("tools"):
                kwargs.pop("json_mode", None)
            return await self.llm.chat(messages, **kwargs)

        retry_invoke = with_retry(
            max_retries=3,
            base_delay=1.0,
            retryable=is_retryable_llm_error,
            on_retry=tracker.note_retry,
        )(_invoke)

        try:
            response = await retry_invoke()
        except Exception as e:
            tracker.fail(e)
            raise
        tracker.succeed(response)
        return response

    async def run(self, **kwargs) -> dict:
        """执行 Agent：构造消息 → 工具调用循环 → 解析响应。

        支持的可选参数：
        - conversation_history: list[dict]，最近对话历史（含 role/content），
          会插入 system 与当前 user 消息之间，让 Agent 具备多轮上下文。
          内部处理，不会传给 build_messages。

        工具调用循环：
        - 若 LLM 返回 tool_calls，执行工具并把结果回填，继续调用
        - 直到 LLM 返回纯文本，或达到 TOOL_LOOP_MAX_ITERATIONS

        Returns:
            解析后的结构化字典。

        Raises:
            asyncio.TimeoutError: LLM 调用超时。
        """
        conversation_history = kwargs.pop("conversation_history", None)
        messages = self.build_messages(**kwargs)
        if conversation_history:
            messages = self._inject_history(messages, conversation_history)
        logger.info(f"[{self.name}] calling LLM with {len(messages)} message(s)")

        tool_defs = self._tool_definitions()
        response: Response | None = None
        prev_tool_names: tuple[str, ...] | None = None

        for iteration in range(TOOL_LOOP_MAX_ITERATIONS + 1):
            response = await asyncio.wait_for(
                self._call_llm(
                    messages,
                    tools=tool_defs or None,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    model=self.model,
                    json_mode=self.json_mode,
                ),
                timeout=AGENT_TIMEOUT,
            )

            # 没有工具调用 → 拿到最终内容，退出循环
            if not response.tool_calls:
                break

            # 防死循环：连续两轮调用完全相同的工具（无进展）→ 强制终止
            names = tuple(tc.name for tc in response.tool_calls)
            if names and names == prev_tool_names:
                logger.warning(
                    f"[{self.name}] 工具调用无进展（重复 {names}），终止工具循环"
                )
                break
            prev_tool_names = names

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

        final_content = response.content or ""
        logger.debug(f"[{self.name}] LLM 原始响应 ({len(final_content)} 字符): {final_content[:500]}")

        # 解析 + 失败修复重试（max_parse_attempts > 1 时生效）：
        # LLM 输出非合法 JSON 时，把原始输出回喂让它修复格式，再解析一次
        result = self.parse_response(final_content)
        attempts = 1
        while result.get("_parse_error") and attempts < self.max_parse_attempts:
            attempts += 1
            logger.warning(
                f"[{self.name}] 输出解析失败，请求 LLM 修复格式（第 {attempts} 次）"
            )
            fix_messages = messages + [
                Message(
                    role=Role.USER,
                    content=(
                        "你上一次的输出无法解析为合法 JSON。请重新输出，严格要求：\n"
                        "1. 只输出一个合法 JSON 对象\n"
                        "2. 不要 Markdown 代码块、注释或任何解释文字\n"
                        f"3. 这是你上一次的输出，请修复其格式后重新输出：\n{final_content[:2000]}"
                    ),
                )
            ]
            fix_response = await asyncio.wait_for(
                self._call_llm(
                    fix_messages,
                    tools=tool_defs or None,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    model=self.model,
                    json_mode=self.json_mode,
                ),
                timeout=AGENT_TIMEOUT,
            )
            final_content = fix_response.content or ""
            result = self.parse_response(final_content)

        return result

    # --- 上下文注入 ---

    @staticmethod
    def _inject_history(
        messages: list[Message], history: list[dict], limit: int = 8
    ) -> list[Message]:
        """把最近对话历史插入 system 与当前 user 消息之间。

        Args:
            messages: build_messages 的输出，约定结构为 [system, user, ...]。
            history: 对话历史列表（{role, content}），只取最近的 limit 条。
            limit: 最多注入的历史消息条数，防止上下文膨胀。

        Returns:
            注入历史后的消息列表。
        """
        injected: list[Message] = []
        for h in history[-limit:]:
            if not isinstance(h, dict):
                continue
            role = h.get("role")
            content = h.get("content", "")
            if not content:
                continue
            if role == "user":
                injected.append(Message(role=Role.USER, content=content))
            elif role in ("assistant", "ai"):
                injected.append(Message(role=Role.ASSISTANT, content=content))

        if not injected or not messages:
            return messages
        # 历史插在 system 消息之后、当前 user 之前；没有 system 则插在最前
        insert_idx = 0
        for i, m in enumerate(messages):
            if m.role == Role.SYSTEM:
                insert_idx = i + 1
                break
        return messages[:insert_idx] + injected + messages[insert_idx:]

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
