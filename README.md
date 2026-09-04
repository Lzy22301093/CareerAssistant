# CareerAssistant — AI 求职助手

基于多 Agent 协作的智能求职辅助系统。用户输入目标岗位 JD 和简历，系统自动完成岗位分析、简历匹配、差距诊断、简历优化、面试题生成、AI 模拟面试等全流程。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + LangGraph（13 节点状态机）+ MySQL + Redis |
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia |
| LLM | 小米 MIMO（OpenAI 兼容协议），快/慢模型分层 |
| 语音 | ASR（语音识别）+ TTS（语音合成），WebSocket 实时通信 |
| 部署 | Docker Compose 四服务（backend / frontend / redis / mysql） |

## 功能概览

### 求职主流程

- **JD 分析** — 提取岗位要求、技能关键词、任职资格
- **简历解析** — 从上传文件中提取结构化个人画像（经历、技能、教育）
- **差距分析** — 对比 JD 与简历，识别匹配项和差距项，给出补强建议
- **简历优化** — 基于 JD 关键词和最佳实践，重写简历内容并量化成果
- **评审迭代** — 规则预检 + LLM 评审，不达标自动重写（最多 2 轮）
- **HTML 渲染** — 生成可下载的专业简历页面
- **面试题生成** — 根据 JD 和简历生成针对性面试题库
- **求职信生成** — 一键生成求职信 / 招聘软件打招呼文案

### AI 模拟面试

- **多轮对话面试** — AI 扮演面试官，根据 JD 和简历提问
- **语音交互** — 支持语音输入（ASR）和语音播报（TTS），WebSocket 实时传输
- **面试评估** — 从专业度、表达、逻辑等维度评分并给出改进建议
- **面试记录** — 自动记录面试过程，生成复习计划

### 智能能力

- **意图分类** — LLM 理解用户意图（上传 JD、修改简历、自由提问等），按意图动态编排执行链
- **增量编辑** — 换岗位 / 补材料时自动检测变化，只重跑受影响的环节
- **跨会话记忆** — 结构化存储用户画像，跨会话持久化
- **RAG 知识库** — 向量检索相似案例和最佳实践，增强生成质量
- **流式输出** — SSE 实时推送执行进度和中间结果

## 系统功能链路

```
用户输入（JD / 简历 / 自然语言）
        │
        ▼
   ┌─────────────┐
   │  意图分类层  │  LLM 识别意图（FAST_MODEL）
   │  (Planner)   │  低置信时回退规则引擎
   └──────┬──────┘
          │  intent ∈ {upload_jd, upload_profile, gap_analysis,
          │            content_edit, render_edit, export,
          │            ask_question, generate_cover_letter,
          │            record_interview}
          ▼
   ┌──────────────────────────────────────────────┐
   │            LangGraph 工作流编排               │
   │                                              │
   │  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
   │  │ JD 分析  │  │ 画像提取 │  │ 差距分析  │  │
   │  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
   │       └──────┬──────┘              │        │
   │              ▼                     │        │
   │       ┌────────────┐              │        │
   │       │ 简历优化   │◄─────────────┘        │
   │       └─────┬──────┘                       │
   │             ▼                               │
   │  ┌──────────────┐  ┌──────────────┐        │
   │  │ LLM 评审     │  │ 面试题生成   │        │
   │  │ (不达标重写) │  │              │        │
   │  └──────┬───────┘  └──────┬───────┘        │
   │         ▼                  │                │
   │  ┌────────────┐           │                │
   │  │ HTML 渲染  │           │                │
   │  └────────────┘           │                │
   └───────────────────────────┼────────────────┘
                               │
          ┌────────────────────┼────────────────┐
          ▼                    ▼                 ▼
   ┌────────────┐    ┌──────────────┐    ┌───────────┐
   │ 面试模拟   │    │  求职信生成  │    │ 自由问答  │
   │ (语音交互) │    │              │    │           │
   └─────┬──────┘    └──────────────┘    └───────────┘
         ▼
   ┌────────────┐
   │ 面试评估   │
   │ + 复习计划 │
   └────────────┘
```

**执行规则**：所有分析节点完成后回到 Planner 重新路由，而非硬编码顺序执行。问题节点和求职信节点直接到 END，不经过评审循环。

## 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone <repo-url> && cd CareerAssistant

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等

# 启动所有服务
docker compose up -d

# 查看后端日志
docker compose logs -f backend
```

服务地址：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

> 本地开发需在 `frontend/.env.local` 设置 `VITE_API_TARGET=http://localhost:8000`

### 运行测试

```bash
cd backend
python -m pytest tests/ -v --ignore=tests/test_tools_integration.py
```

## 项目结构

```
backend/app/
  agents/          # 12 个 LLM Agent（JD 分析、画像提取、差距分析、简历优化、面试 QA 等）
  graph/           # LangGraph 工作流（节点、边、状态、意图分类、调度）
  interview/       # AI 模拟面试子图（独立状态机）
  voice/           # 语音服务（ASR 识别、TTS 合成、WebSocket 网关）
  api/             # FastAPI 路由（认证、会话、偏好、面试）
  models/          # ORM 模型、Pydantic Schema、Session Store
  llm/             # LLM 抽象层（OpenAI 兼容、重试、可观测）
  tools/           # 工具集（文件解析、知识检索、模板渲染）
  rag/             # RAG 服务（Embedding + 向量检索）
  prompts/         # Prompt 模板（意图分类、面试记录、记忆整合）
  services/        # 业务服务（记忆、面试记录、导出）

frontend/src/
  views/           # 页面（首页、登录、注册）
  components/      # 组件（对话面板、结果面板、语音面试、历史记录）
  stores/          # Pinia 状态管理（会话、认证）
  api/             # HTTP 客户端 + SSE 流式解析
```

## Agent 清单

| Agent | 职责 | 模型 |
|-------|------|------|
| planner | 意图识别 + 任务编排 | PRO |
| jd_analyzer | 岗位要求提取 | FAST |
| profile_extractor | 简历画像提取 | FAST |
| gap_analyzer | 差距分析 + 补强建议 | FAST |
| content_generator | 简历内容优化 | PRO |
| reviewer | 简历质量评审 | FAST |
| html_renderer | HTML 简历渲染 | PRO |
| interview_qa | 面试题生成 | PRO |
| interview_reviewer | 面试题评审 | FAST |
| cover_letter | 求职信生成 | PRO |
| clarifier | 澄清追问 | FAST |
| question | 自由问答 | FAST |
| interviewer | AI 面试官 | PRO |
| evaluator | 面试评估 | FAST |

> **模型分层**：通过 `FAST_MODEL` 环境变量启用。FAST = `mimo-v2.5`（提取/评审类，快且便宜），PRO = `mimo-v2.5-pro`（生成类，质量优先）。未配置 `FAST_MODEL` 时所有 Agent 均使用 PRO。Docker Compose 默认设为 `mimo-v2.5`。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API 密钥 | — |
| `LLM_BASE_URL` | LLM 接口地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 生成类模型 | `mimo-v2.5-pro` |
| `FAST_MODEL` | 提取类模型 | `mimo-v2.5` |
| `DATABASE_URL` | MySQL 连接串 | `mysql+pymysql://career:career@mysql:3306/career_assistant` |
| `REDIS_URL` | Redis 地址 | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | `change-me-in-production` |
| `GRAPH_TIMEOUT` | 工作流总超时（秒） | `600` |

## 文档

- [架构设计 v3](docs/architecture-v3.md) — 当前系统蓝本
- [架构设计 v2](docs/architecture-v2.md) — 原始设计
- [部署指南](docs/DEPLOYMENT.md) — 三种部署模式 + FAQ
- [实施计划](docs/implementation-plan.md) — 开发进度记录

## License

MIT
