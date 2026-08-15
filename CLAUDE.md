# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 联网搜索规则（重要）

**禁止使用内置 WebSearch 工具**，它在当前环境下不可用。

需要搜索网页时，必须使用以下方式之一：

- Firecrawl MCP 工具：`mcp__firecrawl__firecrawl_search`
- Firecrawl CLI：`npx firecrawl-cli search "关键词" --limit N`

需要抓取网页内容时，使用：

- Firecrawl MCP 工具：`mcp__firecrawl__firecrawl_scrape`
- Firecrawl CLI：`npx firecrawl-cli scrape "URL"`

## 项目定位

AI 求职助手：用户输入 JD + 简历，多 Agent 协作完成分析、匹配、简历生成、面试准备。

- 后端：FastAPI + LangGraph（10 个 Agent 状态机）+ MySQL + Redis
- 前端：Vue 3 + TypeScript + Element Plus + Pinia
- LLM：小米 MIMO（OpenAI 兼容协议），配置见 `backend/app/config.py`
- 部署：Docker Compose 四服务（backend, frontend, redis, mysql）

## 常用命令

```bash
# Docker（推荐）
docker compose up -d                    # 启动，MySQL 映射到宿主机 3307
docker compose logs -f backend          # 查后端日志
docker compose build --no-cache backend # Windows volume 不同步时用这个

# 后端本地
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# 前端本地（需在 frontend/.env.local 设置 VITE_API_TARGET=http://localhost:8000）
cd frontend && npm install && npm run dev

# 测试
cd backend && python -m pytest tests/ -v --ignore=tests/test_tools_integration.py
```

## 关键目录

```text
backend/app/
  agents/       # 10 个 LLM Agent（继承 BaseAgent，部分带工具调用）
  graph/        # LangGraph 工作流（workflow.py 是入口，nodes.py 是节点，edges.py 是路由）
  api/          # FastAPI 路由（health, auth, preferences, sessions）
  models/       # ORM（orm.py）、Pydantic schemas（schemas.py）、session store
  llm/          # LLM 抽象层（OpenAI 兼容，带重试）
  tools/        # 文件解析、信息提取、模板渲染等工具
  rag/          # RAG 服务（embedding + 向量检索）

frontend/src/
  stores/       # Pinia 状态（session.ts 是核心，auth.ts 是认证）
  api/          # axios 客户端 + SSE 流式解析（sessions.ts 的 sendMessageSSE）
  components/   # ChatPanel（对话）、ResultPanel（5 个 Tab 展示结果）
```

## 非显而易见的约束

- LangGraph 工作流中，所有分析节点完成后**回到 Planner 重新路由**，而非硬编码边顺序执行
- `interview_questions` 在 session 中存储为 `{questions: [...]}` 结构，前端需 `.questions` 取数组
- SSE 事件中 `clarification` 的消息字段是 `question`（非 `content`）
- Agent 超时 120 秒（MIMO API 响应慢），见 `backend/app/agents/base.py` 的 `AGENT_TIMEOUT`；整图总超时 `GRAPH_TIMEOUT`（默认 600s，`sessions.py` 的 `_graph_stream` 逐块倒计时）
- 表在后端启动时自动创建（`main.py` 的 `on_startup`），`init_db.py` 需导入所有 ORM 模型
- pytest 配置 `asyncio_mode = auto`，async 测试无需手动加装饰器
- 前端 vite proxy 通过 `VITE_API_TARGET` 环境变量切换 Docker/本地模式

### 模型分层（性能）

- `FAST_MODEL`（默认 `mimo-v2.5`）给提取/评审/澄清类 Agent（jd_analyzer、profile_extractor、gap_analyzer、reviewer、interview_reviewer、clarifier），`LLM_MODEL`（`mimo-v2.5-pro`）给生成类（content_generator、html_renderer、interview_qa）
- 分层在 `create_agents`（`agents/__init__.py`）通过 `model=fast_model` 注入；`BaseAgent` 的 `temperature`/`max_tokens`/`model` 按 Agent 类属性配置，`run()` 透传给 provider（`openai_provider.chat` 支持 per-call `model` 覆盖）
- 提取类 Agent 的 prompt 输入统一经 `backend/app/tools/context.py` 的 `compact_*` 函数裁剪（限制条数 + 截断长文本），不要绕开它直接塞全量 JSON

### 工具调用

- `BaseAgent.run()` 内置 tool-calling 循环（上限 `TOOL_LOOP_MAX_ITERATIONS=5`）：调 LLM → 执行工具 → 结果回填 → 再调
- 已绑定工具的 Agent：`gap_analyzer`（similar_cases/RAG）、`interview_qa`（question_bank）、`content_generator`（best_practices/keyword_optimizer/template_search）
- 工具定义在 `tools/__init__.py` 的 `create_all_tools`，但**真正接线在 `create_agents`**；给新 Agent 加工具时两处都要看

### 图结构与评审循环

- 图节点：planner → parallel_analysis(jd∥profile) → gap → content → **parallel_post（评审∥面试题生成）** → html_renderer → interview_reviewer → END
- `reviewer_node` 先跑规则预检（`_rule_based_review_check`：板块完整+量化数字+关键词覆盖≥30%），通过则跳过 LLM 评审
- 评审迭代上限 `MAX_ITERATIONS=2`（`graph/reflection.py`），阈值 `PASS_SCORE=75`
- `parallel_post_node` 只在面试题不存在时生成（评审迭代期间不重复生成）

### 会话与流式

- `sessions.py` 按 session_id 有并发锁（`asyncio.Lock`），同会话消息串行处理，防止读-改-写竞态；锁在 SSE 流结束时释放
- `send_message` 用 `graph.astream(stream_mode="updates")` 流式推送：每节点发 `progress`（中文文案）+ 产物事件（jd_analysis/profile/...），前端 `session.ts` 的 progress 单行替换不刷屏
- `graph_state` 必须带上 `clarification_history`/`ready_to_proceed`/`uploaded_files`/`content_iterations` 等字段，否则 Clarifier 多轮与文件兜底逻辑失忆

### 安全

- 密钥（`OPENAI_API_KEY`/`JWT_SECRET_KEY`）不写死代码，通过 `.env`/环境变量注入；`Settings` 配置了 `extra="ignore"` 容忍 docker compose 专用变量
- `with_retry` 区分错误类型：429/连接/5xx 重试（429 延长退避），401/400/422 快速失败（`llm/retry.py` 的 `is_retryable_llm_error`）

## 详细文档

文档索引：`docs/README.md` · 架构设计：`docs/architecture-v2.md` · 部署指南：`docs/DEPLOYMENT.md` · 实施计划：`docs/implementation-plan.md`
