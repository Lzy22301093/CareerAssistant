# AGENTS.md

本文件供 ZCode / 自动化 Agent 在本仓库执行长任务时使用，只收录**长期有效的项目级规则**。
当前进度、一次性任务、交接状态记录在**本地过程文档**（`docs/handoff.md`、`docs/implementation-plan.md`，仅存本机不入库），不要写进本文件。

## 1. 项目目标

AI 求职助手（CareerAssistant）：用户输入目标岗位 JD 与简历，多 Agent 协作完成岗位分析、差距诊断、简历优化、HTML 简历渲染、面试题生成、AI 模拟面试（含语音）、求职信生成、跨会话长期陪伴。

当前产品方向（长期有效）：从"聊天为中心"演进为"**个人画像驱动的资产工作台**"——核心原则：

1. 画像先于生成（所有产物基于结构化画像而非原始文本）
2. 证据优先（画像条目可溯源到上传材料）
3. 用户拥有最终写入权（改动走"提案 → 用户确认"闭环，拒绝提案时原画像不变）
4. 一次输入多处复用（JD/简历录入一次，全流程复用）
5. 先做可控闭环，再做自主 Agent

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + LangGraph + SQLAlchemy 2 + Pydantic / pydantic-settings |
| 数据库 | MySQL 8（Docker 内 3306，宿主机映射 3307）；Redis 7（可选，缺失时回退内存存储） |
| LLM | OpenAI 兼容协议（小米 MIMO）。`LLM_MODEL`（PRO，生成类）+ `FAST_MODEL`（提取/评审/分类类）；ASR/TTS 模型共享同一 base_url/api_key |
| 前端 | Vue 3（`<script setup lang="ts">`）+ TypeScript + Element Plus + Pinia + Vue Router + Vite；图标用 `lucide-vue-next`，不用 emoji 当图标 |
| 认证 | JWT（pyjwt）+ bcrypt |
| 部署 | Docker Compose 四服务：backend / frontend / redis / mysql |

## 3. 项目结构

```text
backend/app/
  agents/       # LLM Agent（BaseAgent 子类；interviewer/evaluator 属模拟面试）
  graph/        # 主工作流：workflow.py(图入口) nodes.py(节点) plan.py(执行计划)
                # scheduler.py intent.py(意图分类) reflection.py(评审循环) state.py trace.py
  interview/    # AI 模拟面试独立子图（graph/edges/nodes/state + handler + session_service）
  voice/        # 语音网关（ASR/TTS 服务、WebSocket handler、协议定义）
  api/          # FastAPI 路由：health auth preferences profile proposals sessions interview
  models/       # orm.py(14 张表) schemas.py init_db.py database.py session_store/redis_session/mysql_store
  llm/          # LLM 抽象层：openai_provider retry(重试分类) structured(schema 校验) observability
  tools/        # 文件解析/知识检索/渲染工具 + context.py 的 compact_* 输入裁剪
  rag/          # Embedding + 向量检索
  prompts/      # Prompt 模板
  services/     # 业务服务（memory/interview_memory/profile/proposal/export/auth 等）
  scripts/      # 数据迁移脚本（migrate_profile.py）

frontend/src/
  views/        # HomePage LoginPage RegisterPage MockInterviewView KnowledgeBaseView FeatureWallView
  components/   # ChatPanel ResultPanel VoiceInterviewPanel KnowledgeNodeGraph AppNav 等
  stores/       # session.ts(核心会话) auth.ts knowledgeBase.ts
  api/          # axios client + SSE 流式解析(sessions.ts) + interview/profile
  composables/  # useVoiceChat.ts
  styles/       # tokens.css / element-overrides.css（视觉改动只在这两层做）

docs/           # 长期契约: agents-contract.md DEPLOYMENT.md；过程文档（handoff/plan 等）仅存本机不入库
逆向工程/        # FResume 产品参考资料，只读，不参与构建
uploads/        # 运行时上传文件，不入 git
```

## 4. 编码约定

- 后端注释、日志、SSE 文案、前端 UI 文案均使用中文。
- 配置统一走 `backend/app/config.py` 的 `Settings`（pydantic-settings），**必须保持 `extra="ignore"`**（容忍 docker compose 专用变量）。
- 密钥（`OPENAI_API_KEY`/`JWT_SECRET_KEY` 等）永不写死在代码/文档中，通过 `.env` 注入；`.env` 不入 git。
- LLM 结构化输出必须经 `llm/structured.py` 做 Pydantic schema 校验，禁止直接 `json.loads` 后裸用。
- 提取类 Agent 的 prompt 输入必须经 `tools/context.py` 的 `compact_*` 函数裁剪，不要直接塞全量 JSON。
- LLM 重试统一交给 `llm/retry.py` 的 `with_retry`（按错误类型分类），SDK 侧 `max_retries=0`。
- **修改 `models/orm.py` 必须同步修改 `models/init_db.py` 的导入**（表在启动时自动创建）；已有库的新表走增量迁移脚本（参考 `scripts/migrate_profile.py`），禁止破坏性 schema 变更。
- 前端类型定义集中在 `frontend/src/types/`，Pinia store 不直接发 axios 请求（走 `src/api/`）。

## 5. 不允许修改 / 破坏的内容

- **能力单元契约**（`docs/agents-contract.md`）：每个 Agent 只写 GraphState 中属于自己的字段，越权写入视为 Bug；单元间不直接互调，由 planner/执行计划调度；单元不直接访问数据库，一律经 GraphState 读写。
- **SSE 事件兼容性**：已有事件名与字段结构（如 `clarification` 的消息字段是 `question` 而非 `content`；`interview_questions` 在 session 中存为 `{questions: [...]}`）是前后端契约，只能新增不能改名。
- **增量重算语义**：`render_config` 永不因输入变化被裁剪；下游产物必须记录"基于版本"（`*_analyzed_version`）。
- **不做清单**：不引入 multi-agent 通信框架；不自研 vector store；招聘大盘、网申插件、订阅计费等不在范围内。
- `逆向工程/` 目录只读。
- `clarifier`、`reviewer`、`graph/reflection.py` 处于"v4 重构待移除"的半拆状态（工作流仍注册 clarifier 节点）——**不要基于它们扩展新功能**，也不要在未确认的情况下贸然删除。

## 6. 重要的架构约束

- **v4 图结构**：`planner → plan_advance` 线性流水线，由 `graph/plan.py` 的 `build_execution_plan` 生成执行计划驱动；各分析节点完成后回到 `plan_advance` 推进，而非硬编码边序；`question`/`cover_letter` 直接到 END。意图路由模式由 `plan_routing_mode` 控制（legacy/shadow/plan_first/plan_only）。
- **意图分类**：`graph/intent.py` 用 FAST_MODEL 做 LLM 意图分类（9 个合法意图），低置信（<0.6）或解析失败回退规则引擎。
- **模型分层**：`create_agents`（`agents/__init__.py`）注入 `fast_model`；Agent 级 `temperature`/`max_tokens`/`model` 是类属性。给新 Agent 接工具时，工具定义在 `tools/`、接线在 `create_agents`，两处都要改。
- **超时链**：单 LLM 请求 110s（`llm_timeout`）< 单 Agent 120s（`AGENT_TIMEOUT`）< 整图 600s（`GRAPH_TIMEOUT`）；tool-calling 循环上限 `TOOL_LOOP_MAX_ITERATIONS=3`；评审迭代上限 `MAX_ITERATIONS=2`、通过分 `PASS_SCORE=75`（`graph/reflection.py`）。
- **会话并发**：`api/sessions.py` 按 session_id 持 `asyncio.Lock`，同会话消息串行处理，锁在 SSE 流结束时释放。
- **模拟面试子系统**：`interview/` 是独立 LangGraph 子图 + REST API；`voice/` 是 WebSocket 网关（`/ws`），Voice Gateway 不碰面试逻辑，Evaluator 不生成问题文本；与主图的 `interview_qa`（题库生成）是共存关系，不互相替代。
- **表自动建**：后端启动时 `main.py` 的 `on_startup` 建表并初始化面试 handler；Redis 缺失时 SessionStore 回退内存实现。

## 7. 本地启动方式

```bash
# Docker（推荐，MySQL 映射宿主机 3307）
docker compose up -d
docker compose logs -f backend

# 后端本地（连接本机/宿主机 MySQL 时用 3307 端口）
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端本地（需先在 frontend/.env.local 设置 VITE_API_TARGET=http://localhost:8000）
cd frontend && npm install && npm run dev
```

服务地址：前端 http://localhost:5173 · 后端 API http://localhost:8000 · API 文档 http://localhost:8000/docs

## 8. 测试方式

```bash
# 后端全量（必须排除集成测试，它需要真实 LLM）
cd backend && python -m pytest tests/ -v --ignore=tests/test_tools_integration.py

# 前端类型检查 + 构建（兼作前端"测试"）
cd frontend && npm run build
```

- pytest 配置 `asyncio_mode = auto`（`backend/pytest.ini`），async 测试无需装饰器。
- 测试全部基于 mock，不需要真实 MySQL/Redis/LLM。
- 当前基线：**后端 568 passed**（2026-09-08 导出保版后实测），前端 `vue-tsc -b && vite build` 通过。

## 9. Docker 使用方式

- `docker compose up -d` 启动；`docker compose logs -f backend` 查日志；`docker compose build --no-cache backend` 在 Windows 上 volume 代码不同步时使用。
- compose 内 backend/frontend 挂载本地源码目录（热更新）；MySQL 宿主机端口是 **3307**（3307:3306），backend 连接串用容器内服务名 `mysql:3306`。
- 根目录 `.env` 供 docker compose 使用；`backend/.env` 供本地 pydantic-settings 使用，两套分工不要混。

## 10. 前后端联调方式

- 前端所有请求走 `/api` 前缀，由 vite proxy 转发到 `VITE_API_TARGET`（默认 Docker 模式 `http://backend:8000`，本地开发设为 `http://localhost:8000`）。
- 主会话消息走 **SSE**（`frontend/src/api/sessions.ts` 的 `sendMessageSSE`），进度事件单行替换不刷屏；语音面试/语音聊天走 **WebSocket**（`/ws`，见 `voice/gateway.py` 与 `useVoiceChat.ts`）。
- 后端 CORS 白名单在 `Settings.cors_origins`，新增前端来源需同步。

## 11. 完成任务前必须进行的验证

1. 后端 `pytest` 全绿，且通过数**不低于当前基线**（新功能必须带测试）。
2. 前端 `npm run build`（vue-tsc 类型检查）通过。
3. 动过 ORM：`init_db.py` 已同步，且为已有数据库准备了增量迁移脚本。
4. 动过 SSE 事件 / GraphState 字段：逐一核对新旧前端对事件与字段的兼容性。
5. 涉及 UI：跑通一次关键路径冒烟（登录 → 会话消息 → 结果面板），视觉改动只用 `styles/tokens.css`、`element-overrides.css` 两层。
6. 按项目惯例把进度回写本地过程文档 `docs/implementation-plan.md`（勾选指令/阶段），必要时更新 `docs/handoff.md`（两份文档仅存本机，不入库）。

## 12. 其他工作约定

- **联网检索**：优先使用 Firecrawl（MCP 工具或 `npx firecrawl-cli`）；内置 WebSearch 在部分环境下不可用或仅限美国区，结果不可依赖。
- **Git**：仓库在 Windows（Git Bash）下使用，行尾为 CRLF 转换模式；提交按功能分批，避免巨型混合提交；未经确认不执行 `git push`。
- **阶段推进节奏**：一次只推进一个阶段/一条指令，验收未达标即停；先数据/后端、后前端；每阶段结束保持测试全绿后再进入下一步。
