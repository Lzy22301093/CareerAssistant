# CareerAssistant

把求职从「到处复制粘贴」变成可复用的个人资产。

CareerAssistant 是一款面向求职全流程的 AI 工作台：以**个人画像**为唯一事实源，生成并维护简历版本，针对具体岗位做匹配与定向改写，用语音模拟面试检验准备度，并把面试反馈安全地沉淀回画像。

## 你可以在里面做什么

- **维护个人画像** — 基本信息、教育、实习/项目、技能、投递方向、软性信息；条目带证据与确认状态
- **生成简历** — 8 步向导：从画像到可导出的专业简历（Word / HTML）
- **管理简历版本** — 简历库多版本、区域框选改写、对比采纳、一键回滚
- **匹配岗位** — 贴 JD 建匹配任务，看分数与差距维度，导出定向草稿
- **模拟面试** — 选定本场简历 + JD，语音多轮面试，出报告与画像更新提案
- **求职分析** — 对话式：分析 JD、诊断差距、改写内容、出面试题、写求职信
- **跟踪投递** — 手动登记投递进度

## 产品原则

1. **画像先于生成** — 简历与面试都基于可追溯的已确认画像
2. **AI 只提议，你拍板** — 改写候选、画像提案不直接覆盖原文
3. **一次输入，多处复用** — 同一段经历可服务简历、匹配、面试追问
4. **版本可回滚** — 简历改动产生新版本，旧版永远可回去

## 模块一览

| 模块 | 路由 | 做什么 |
|------|------|--------|
| 个人画像 | `/knowledge-base` | 事实源：条目、证据、投递方向、软性信息 |
| 简历生成 | `/resume-generation` | 8 步向导，从画像出一版简历 |
| 简历工作台 | `/resume-library` | 改已有简历：多版本、区域改写、岗位匹配 |
| 模拟面试 | `/mock-interview` | JD + 本场简历驱动的语音面试与报告 |
| 求职分析 | `/workspace` | 对话协作：分析、差距、改稿、面试题、求职信 |
| 投递记录 | `/applications` | 手动跟踪投递状态 |

## 端到端闭环

```text
个人画像 (confirmed)
    │
    ├─► 简历生成向导 ──► 简历库 (版本 / 区域改写)
    │                        │
    ├─► 岗位匹配 (JD 资产) ──┤
    │                        │
    └─► 模拟面试 (JD+简历) ──► 报告 / 画像提案 ──用户确认──┘
                              │
                         求职分析（对话式草稿与问答）
```

## 快速开始

### Docker 部署（推荐）

```bash
git clone <repo-url> && cd CareerAssistant

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等

docker compose up -d
docker compose logs -f backend

# 已有数据库时执行一次性迁移（新库表会自动创建）
docker compose exec backend python -m scripts.migrate_profile --apply
docker compose exec backend python -m scripts.migrate_resume_library --apply
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

# 前端（另开终端；需 frontend/.env.local 设 VITE_API_TARGET=http://localhost:8000）
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
# 后端（排除需真实 LLM 的集成测试）
cd backend
python -m pytest tests/ -v --ignore=tests/test_tools_integration.py

# 前端类型检查 + 构建
cd frontend
npm run build
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python · FastAPI · LangGraph · SQLAlchemy · MySQL · Redis（可选） |
| 前端 | Vue 3 · TypeScript · Element Plus · Pinia · Vite |
| LLM | OpenAI 兼容协议（生成 / 提取双模型分层） |
| 语音 | ASR + TTS · WebSocket（模拟面试、语音对话） |
| 部署 | Docker Compose：backend / frontend / redis / mysql |

## 引擎能力（简要）

前端之下是一套可增量重算的 Agent 工作流：

- **意图分类** — 理解「贴 JD / 补材料 / 改内容 / 出题 / 写求职信」等意图，编排执行链
- **增量重算** — 输入变化时只重跑受影响环节，保留模板等无关状态
- **结构化输出** — LLM 结果经 schema 校验后再落库
- **流式反馈** — SSE 实时推送进度与中间产物
- **跨会话记忆** — 画像条目与证据沉淀，供后续生成复用

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API 密钥 | — |
| `LLM_BASE_URL` | LLM 接口地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 生成类模型 | `mimo-v2.5-pro` |
| `FAST_MODEL` | 提取 / 评审类模型 | `mimo-v2.5` |
| `DATABASE_URL` | MySQL 连接串 | `mysql+pymysql://career:career@mysql:3306/career_assistant` |
| `REDIS_URL` | Redis 地址 | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | `change-me-in-production` |
| `GRAPH_TIMEOUT` | 工作流总超时（秒） | `600` |

## 文档

- [部署指南](docs/DEPLOYMENT.md) — 三种部署模式 + FAQ

## License

MIT
