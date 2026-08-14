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

- 后端：FastAPI + LangGraph（9 个 Agent 状态机）+ MySQL + Redis
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
  agents/       # 9 个 LLM Agent（继承 BaseAgent）
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
- Agent 超时 120 秒（MIMO API 响应慢），见 `backend/app/agents/base.py` 的 `AGENT_TIMEOUT`
- 表在后端启动时自动创建（`main.py` 的 `on_startup`），`init_db.py` 需导入所有 ORM 模型
- pytest 配置 `asyncio_mode = auto`，async 测试无需手动加装饰器
- 前端 vite proxy 通过 `VITE_API_TARGET` 环境变量切换 Docker/本地模式

## 详细文档

文档索引：`docs/README.md` · 架构设计：`docs/architecture-v2.md` · 部署指南：`docs/DEPLOYMENT.md` · 实施计划：`docs/implementation-plan.md`
