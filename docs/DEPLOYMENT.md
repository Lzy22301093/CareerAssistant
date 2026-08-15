# 项目启动与关闭指南

## 目录

- [项目结构总览](#项目结构总览)
- [环境要求](#环境要求)
- [配置文件说明](#配置文件说明)
- [方式一：全 Docker 启动（推荐）](#方式一全-docker-启动推荐)
- [方式二：混合模式（Docker 数据库 + 本机后端/前端）](#方式二混合模式docker-数据库--本机后端前端)
- [方式三：全本机启动](#方式三全本机启动)
- [关闭与清理](#关闭与清理)
- [常用运维命令](#常用运维命令)
- [健康检查](#健康检查)
- [常见问题](#常见问题)

---

## 项目结构总览

```
CareerAssistant/
├── .env                    ← Docker 用的环境变量（docker-compose.yml 读取）
├── docker-compose.yml      ← 全栈编排（MySQL + Redis + Backend + Frontend）
├── backend/
│   ├── .env                ← 本机开发用的环境变量（uvicorn 读取）
│   ├── .env.example        ← 环境变量模板
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/                ← FastAPI 后端代码
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/                ← Vue 3 前端代码
└── docs/
    └── DEPLOYMENT.md       ← 本文档
```

---

## 环境要求

| 方式 | 依赖 |
|------|------|
| 全 Docker | Docker 20.10+、Docker Compose 2.0+ |
| 混合模式 | Docker（数据库）+ Python 3.12+、Node.js 20+（本机） |
| 全本机 | Python 3.12+、Node.js 20+、MySQL 8.0+、Redis 7+ |

---

## 配置文件说明

项目有**两个 `.env` 文件**，用途不同：

| 文件 | 读取者 | 用途 |
|------|--------|------|
| `CareerAssistant/.env` | `docker-compose.yml` | Docker 容器的环境变量 |
| `CareerAssistant/backend/.env` | 后端 `pydantic-settings` | 本机直接跑 `uvicorn` 时的配置 |

**核心环境变量（两个文件共用）：**

| 变量 | 说明 | 当前值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API 密钥 | 已配置（**不写死在代码里**，缺失时后端启动报错） |
| `LLM_BASE_URL` | LLM API 地址 | `https://token-plan-cn.xiaomimimo.com/v1` |
| `LLM_MODEL` | 主模型（生成类 Agent 用） | `mimo-v2.5-pro` |
| `FAST_MODEL` | 快速模型（提取/评审/澄清类 Agent 用），为空回退 `LLM_MODEL` | `mimo-v2.5` |
| `GRAPH_TIMEOUT` | 整条工作流总超时（秒） | `600` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 已配置 |
| `DATABASE_URL` | MySQL 连接串（仅 backend/.env） | `mysql+pymysql://career:career@localhost:3307/career_assistant` |
| `REDIS_URL` | Redis 地址（仅 backend/.env） | `redis://localhost:6379/0` |

> 模型分层说明：JD 分析、画像提取、差距分析、评审、澄清等**提取类**任务用 `FAST_MODEL`（更快更省）；简历生成、HTML 渲染、面试题生成等**生成类**任务用 `LLM_MODEL`（质量优先）。

---

## 方式一：全 Docker 启动（推荐）

适合快速体验，一条命令搞定全部。

### 启动

```bash
cd d:/Project/CareerAssistant

# 首次启动（构建镜像 + 启动全部容器）
docker compose up -d

# 查看启动状态
docker compose ps
```

启动后访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost:5173 | 注册/登录后使用 |
| 后端 API | http://localhost:8000 | FastAPI 服务 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| MySQL | localhost:3307 | 自动建库建用户（容器内 3306，映射到宿主机 3307） |
| Redis | localhost:6379 | 会话缓存 |

### 关闭

```bash
# 停止所有容器（保留数据）
docker compose down
```

### 清理数据重来

```bash
# 停止并删除数据卷（MySQL 数据、Redis 缓存全部清除）
docker compose down -v
```

---

## 方式二：混合模式（Docker 数据库 + 本机后端/前端）

适合开发调试，后端代码改了能热重载。

### 第一步：启动数据库

```bash
cd d:/Project/CareerAssistant

# 只启动 MySQL 和 Redis
docker compose up -d mysql redis

# 确认就绪
docker compose ps
```

MySQL 容器会自动：
- 创建数据库 `career_assistant`
- 创建用户 `career`，密码 `career`
- 端口映射到本机 `3306`

### 第二步：启动后端

```bash
cd d:/Project/CareerAssistant/backend

# 安装依赖（首次）
pip install -r requirements.txt

# 启动（--reload 改代码自动重启）
python -m uvicorn app.main:app --reload --port 8000
```

后端读取 `backend/.env`，已配置好连接 `localhost:3306`（Docker 映射出来的端口）。

### 第三步：启动前端

```bash
cd d:/Project/CareerAssistant/frontend

# 安装依赖（首次）
npm install

# 启动
npm run dev
```

### 关闭

```bash
# 停止前端：Ctrl+C

# 停止后端：Ctrl+C

# 停止数据库
docker compose down
```

---

## 方式三：全本机启动

需要本机安装 MySQL 和 Redis。

### 第一步：MySQL

```bash
# 登录 MySQL
mysql -u root -p

# 执行建库建用户
CREATE DATABASE career_assistant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'career'@'localhost' IDENTIFIED BY 'career';
GRANT ALL PRIVILEGES ON career_assistant.* TO 'career'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 第二步：Redis

```bash
redis-server
```

### 第三步：后端

```bash
cd d:/Project/CareerAssistant/backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 第四步：前端

```bash
cd d:/Project/CareerAssistant/frontend
npm install
npm run dev
```

### 关闭

按 `Ctrl+C` 逐个停止，或关闭终端窗口。

---

## 关闭与清理

| 场景 | 命令 |
|------|------|
| 停止全部容器（保留数据） | `docker compose down` |
| 停止并删除数据卷 | `docker compose down -v` |
| 只停止某个容器 | `docker compose stop backend` |
| 重启某个容器 | `docker compose restart backend` |
| 重新构建并启动 | `docker compose up -d --build` |
| 查看容器日志 | `docker compose logs -f backend` |
| 进入容器 shell | `docker compose exec backend bash` |

---

## 常用运维命令

### 查看日志

```bash
# 全部日志
docker compose logs -f

# 只看后端
docker compose logs -f backend

# 只看最近 50 行
docker compose logs --tail 50 backend
```

### 进入容器调试

```bash
# 进入后端容器
docker compose exec backend bash

# 进入 MySQL 容器
docker compose exec mysql mysql -u career -pcareer career_assistant

# 进入 Redis 容器
docker compose exec redis redis-cli
```

### 代码更新后重新部署

```bash
# 拉取最新代码
git pull

# 重新构建镜像并启动
docker compose up -d --build
```

### 运行测试

```bash
# 在本机跑后端测试（不依赖 Docker）
cd backend
python -m pytest tests/ -v --ignore=tests/test_tools_integration.py
```

---

## 健康检查

### 后端 API

```bash
curl http://localhost:8000/health
# 返回: {"status": "ok", "store_type": "redis"} 或 {"status": "ok", "store_type": "memory"}
```

### MySQL

```bash
docker compose exec mysql mysqladmin ping -h localhost
# 返回: mysqld is alive
```

### Redis

```bash
docker compose exec redis redis-cli ping
# 返回: PONG
```

### 查看所有容器状态

```bash
docker compose ps
```

---

## 常见问题

### Q: 端口被占用

```
Error: bind: address already in use
```

```bash
# 查看谁占了端口
netstat -ano | findstr :8000    # Windows
lsof -i :8000                   # Mac/Linux

# 方案 A：停掉占用进程
# 方案 B：改 docker-compose.yml 里的端口映射，如 "8001:8000"
```

### Q: MySQL 容器启动失败

```bash
# 清除旧数据卷重新来
docker compose down -v
docker compose up -d mysql
docker compose logs mysql
```

### Q: 后端连不上 MySQL

Docker 模式下后端依赖 MySQL 健康检查通过才启动。如果仍失败：

```bash
# 检查 MySQL 是否就绪
docker compose ps
docker compose logs mysql

# 手动测试连接
docker compose exec backend python -c "
from sqlalchemy import create_engine
engine = create_engine('mysql+pymysql://career:career@mysql:3306/career_assistant')
conn = engine.connect()
print('连接成功')
conn.close()
"
```

### Q: Redis 连不上

Redis 是**可选的**。连不上时后端自动回退到内存存储，功能不受影响，只是会话不持久化。

### Q: 前端白屏

```bash
# 检查前端是否启动
docker compose logs frontend

# 检查后端 API 是否可访问
curl http://localhost:8000/health
```

### Q: LLM 调用失败

```bash
# 确认 API Key 正确
# Docker 模式：检查根目录 .env
# 本机模式：检查 backend/.env

# 测试 LLM 连接
docker compose exec backend python -c "
from app.config import settings
print('API Key:', settings.openai_api_key[:10] + '...')
print('Base URL:', settings.llm_base_url)
print('Model:', settings.llm_model)
print('Fast Model:', settings.fast_model)
"
```

### Q: 从项目根目录启动后端报 pydantic 校验错误

根目录 `.env` 里有 `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` 等 docker compose 专用变量，
`Settings` 已配置 `extra="ignore"` 忽略它们。若仍报错，检查 `backend/app/config.py` 的
`model_config` 是否保留了 `extra="ignore"`。

### Q: 数据库表不存在

后端首次启动时自动建表。如果表丢失：

```bash
# Docker 模式
docker compose exec backend python -c "
from app.models.database import engine, Base
from app.models import orm
Base.metadata.create_all(engine)
print('表已创建')
"
```

### Q: 忘记密码 / 重新注册

数据在 MySQL 数据卷中。清空重来：

```bash
docker compose down -v
docker compose up -d
```

---

## 服务依赖关系

```
Frontend (5173) ──→ Backend (8000) ──→ MySQL (3306)
                         │
                         └──→ Redis (6379)  [可选]
```

- Frontend 调用 Backend API（`/api/*` 通过 Vite proxy 转发）
- Backend 连接 MySQL 存储用户、会话、简历数据
- Backend 连接 Redis 做会话缓存（不连则回退内存）
- MySQL 和 Redis 都是可选的，缺失时系统降级运行
