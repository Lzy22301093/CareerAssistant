# CareerAssistant Agent 架构设计 v2

> **设计日期**: 2026-08-05
> **设计原则**: 方案 A（最小改动）+ 项目需求驱动
> **状态**: 待评审

---

## 一、设计目标

### 1.1 核心目标

构建一个**真正实用的求职助手**，而不是一个"Agent 玩具"。

```
用户输入 JD → 系统分析 → 用户补充材料 → 系统生成简历 → 用户反馈 → 迭代优化
```

### 1.2 设计原则

1. **需求驱动**：任何设计都应服务于"帮用户找到好工作"
2. **实用优先**：不要为了 Agent 而 Agent，简单任务用简单方案
3. **渐进增强**：先跑通核心流程，再添加高级功能
4. **可扩展**：未来可以轻松添加新 Agent 和新工具

### 1.3 不做什么

- ❌ 不做通用 Agent 框架
- ❌ 不做复杂的任务分解
- ❌ 不做 Agent 间自由对话（初期）
- ❌ 不做自主学习（初期）

---

## 二、整体架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户界面 (Vue 3)                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ ChatPanel│  │ JD Tab   │  │Resume Tab│  │Interview │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI 后端                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API 层                                    │   │
│  │  POST /api/chat  GET /api/session  POST /api/export         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   LangGraph 编排层                                   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Planner Agent                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │   │
│  │  │ 意图识别     │  │ 任务规划    │  │ 状态感知    │          │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    │                               │
│                                    ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Agent Pool                                │   │
│  │                                                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │   │
│  │  │   JD    │  │ Profile │  │  Gap    │  │Content  │         │   │
│  │  │ Analyzer│  │Extractor│  │Analyzer │  │Generator│         │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │   │
│  │       │            │            │            │               │   │
│  │       ▼            ▼            ▼            ▼               │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │   │
│  │  │ Render  │  │Interview│  │ Reviewer│  │Clarifier│         │   │
│  │  │ Agent   │  │   QA    │  │ (新增)  │  │ (新增)  │         │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                    │                               │
│                                    ▼                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Shared Infrastructure                     │   │
│  │                                                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │   │
│  │  │  Tools  │  │ Memory  │  │   RAG   │  │  Trace  │         │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    存储层                                            │
│  ┌─────────────┐              ┌─────────────┐                       │
│  │    Redis    │              │    MySQL    │                       │
│  │  (会话状态) │              │  (持久化)   │                       │
│  └─────────────┘              └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 数量 |
|------|------|------|
| **Planner** | 意图识别 + 任务规划 + 路由 | 1 |
| **Worker Agent** | 执行具体任务 | 7 |
| **Tool** | 外部能力调用 | 5+ |
| **Memory** | 状态管理 + 记忆 | 1 套 |
| **RAG** | 知识检索 | 1 套 |

---

## 三、Agent 设计

### 3.1 Agent 分类

根据项目需求，将 Agent 分为三类：

| 类型 | 特点 | 循环 | 示例 |
|------|------|------|------|
| **Router Agent** | 只做路由，不做业务 | ❌ | Planner |
| **Extractor Agent** | 提取结构化信息 | ❌ | JD Analyzer, Profile Extractor |
| **Generator Agent** | 生成内容，需要迭代 | ✅ | Content Generator, Interview QA |

### 3.2 Agent 基类设计

```python
class BaseAgent:
    """Agent 基类"""
    
    # 基础属性
    name: str
    llm: LLMProvider
    tools: list[Tool]
    memory: Memory
    
    # 核心方法（子类实现）
    async def execute(self, state: GraphState) -> GraphState:
        """执行 Agent 任务"""
        pass
    
    # 可选方法（需要循环的 Agent 覆盖）
    async def execute_with_loop(self, state: GraphState) -> GraphState:
        """带循环的执行（默认无循环）"""
        return await self.execute(state)
```

### 3.3 各 Agent 详细设计

#### 3.3.1 Planner Agent（路由器）

**职责**：
- 识别用户意图
- 感知当前状态
- 决定下一个 Agent

**设计要点**：
- ❌ 不做任务分解（项目流程固定）
- ❌ 不需要循环（路由决策一次就够）
- ✅ 需要状态感知（知道当前进度）

**输入**：
```python
{
    "user_message": "帮我分析这个 JD",
    "stage": "init",
    "has_jd": False,
    "has_profile": False,
    "has_resume": False
}
```

**输出**：
```python
{
    "route": "jd_analyzer",
    "reason": "用户上传了 JD",
    "confidence": 0.95
}
```

**路由表**：
```python
ROUTE_TABLE = {
    "upload_jd": "jd_analyzer",
    "upload_profile": "profile_extractor",
    "analyze_gap": "gap_analyzer",
    "generate_resume": "content_generator",
    "render_resume": "render_agent",
    "generate_interview": "interview_qa",
    "ask_question": "clarifier",
    "review": "reviewer"
}
```

#### 3.3.2 JD Analyzer Agent（提取器）

**职责**：
- 解析职位描述
- 提取结构化信息

**设计要点**：
- ❌ 不需要循环（提取任务一次就够）
- ✅ 需要工具（解析文件）
- ✅ 需要输出验证

**工具依赖**：
- `file_parser`：解析 PDF/DOCX 文件
- `text_cleaner`：清理文本

**输入**：
```python
{
    "jd_text": "We are looking for a Python developer..."
}
```

**输出**：
```python
{
    "job_title": "Python Developer",
    "company": "Tech Corp",
    "requirements": [
        {"category": "skill", "content": "Python 3.10+", "importance": "high"},
        {"category": "experience", "content": "3+ years", "importance": "high"}
    ],
    "keywords": ["Python", "FastAPI", "PostgreSQL"],
    "summary": "Looking for experienced Python developer..."
}
```

#### 3.3.3 Profile Extractor Agent（提取器）

**职责**：
- 从简历/材料中提取候选人信息
- 结构化存储

**设计要点**：
- ❌ 不需要循环
- ✅ 需要工具（解析简历）
- ✅ 需要增量更新（多次补充材料）

**工具依赖**：
- `resume_parser`：解析简历文件
- `entity_extractor`：提取实体信息

**输入**：
```python
{
    "resume_text": "John Doe, 5 years Python experience...",
    "existing_profile": {}  # 已有信息（增量更新）
}
```

**输出**：
```python
{
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["Python", "FastAPI", "SQLAlchemy"],
    "experience": [
        {
            "company": "Corp A",
            "title": "Senior Developer",
            "duration": "2020-2024",
            "highlights": ["Led team of 5", "Built microservices"]
        }
    ],
    "projects": [...],
    "education": [...]
}
```

#### 3.3.4 Gap Analyzer Agent（提取器）

**职责**：
- 对比 JD 和 Profile
- 识别差距和优势

**设计要点**：
- ❌ 不需要循环（分析任务一次就够）
- ✅ 需要工具（查询行业标准）
- ✅ 需要 RAG（参考类似案例）

**工具依赖**：
- `industry_standards`：查询行业标准
- `similar_cases`：参考类似案例

**输入**：
```python
{
    "job": { ... },      # JD 分析结果
    "profile": { ... }   # 候选人画像
}
```

**输出**：
```python
{
    "overall_score": 75.5,
    "gaps": [
        {
            "category": "skill",
            "requirement": "Docker",
            "current_level": "basic",
            "gap_severity": "major",
            "suggestion": "建议学习 Docker 容器化"
        }
    ],
    "strengths": ["Python 经验丰富", "有团队管理经验"],
    "recommendations": ["补充 Docker 经验", "量化项目成果"]
}
```

#### 3.3.5 Content Generator Agent（生成器 + 循环）

**职责**：
- 生成简历内容
- 根据反馈迭代优化

**设计要点**：
- ✅ **需要循环**（生成 → 评估 → 修正）
- ✅ 需要工具（查询模板、参考案例）
- ✅ 需要 Reflection（自我评估）
- ✅ 需要 Memory（记住用户偏好）

**循环流程**：
```
┌─────────────────────────────────────────────────────┐
│                    Agent Loop                        │
│                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │ Generate │───▶│ Evaluate│───▶│ Reflect │         │
│  └─────────┘    └─────────┘    └─────────┘         │
│       ▲                                  │           │
│       │                                  ▼           │
│       │                            ┌─────────┐       │
│       └────────────────────────────│  Revise │       │
│                                    └─────────┘       │
│                                                      │
│  终止条件：                                          │
│  1. quality_score >= 0.8                             │
│  2. iterations >= 3                                  │
│  3. user_satisfied = True                            │
└─────────────────────────────────────────────────────┘
```

**工具依赖**：
- `template_search`：搜索简历模板
- `best_practices`：查询最佳实践
- `keyword_optimizer`：优化关键词

**输入**：
```python
{
    "job": { ... },
    "profile": { ... },
    "gap_analysis": { ... },
    "user_instructions": "突出我的 Python 经验",
    "previous_version": None  # 上一版本（如果有）
}
```

**输出**：
```python
{
    "sections": [
        {
            "title": "Professional Summary",
            "content": "Experienced Python developer with 5+ years..."
        },
        {
            "title": "Skills",
            "content": "Python, FastAPI, SQLAlchemy, Docker..."
        }
    ],
    "metadata": {
        "quality_score": 0.85,
        "iterations": 2,
        "improvements": ["增加了量化指标", "优化了关键词密度"]
    }
}
```

#### 3.3.6 Render Agent（生成器）

**职责**：
- 生成渲染配置
- 生成 HTML 简历

**设计要点**：
- ✅ 需要循环（配置 → 预览 → 调整）
- ✅ 需要工具（HTML 渲染）

**工具依赖**：
- `html_renderer`：渲染 HTML
- `css_generator`：生成样式

#### 3.3.7 Interview QA Agent（生成器 + 循环）

**职责**：
- 生成面试题
- 生成参考答案

**设计要点**：
- ✅ **需要循环**（生成 → 评估 → 补充）
- ✅ 需要 RAG（搜索真实面试题）
- ✅ 需要工具（查询题库）

**循环流程**：
```
生成 5 道题 → 评估覆盖度 → 不够 → 补充 3 道 → 评估 → 够了 → 结束
```

**工具依赖**：
- `question_bank`：查询题库
- `industry_questions`：行业面试题

#### 3.3.8 Reviewer Agent（新增 - 生成器）

**职责**：
- 审查生成的内容
- 提供改进建议

**设计要点**：
- ✅ 需要循环（审查 → 修正 → 再审查）
- ✅ 需要 Reflection（多维度评估）

**评估维度**：
- 完整性：是否覆盖 JD 要求
- 准确性：信息是否准确
- 专业性：用词是否专业
- 一致性：各部分是否一致

#### 3.3.9 Clarifier Agent（新增 - 交互器）

**职责**：
- 向用户提问
- 收集缺失信息

**设计要点**：
- ❌ 不需要循环（提问一次就够）
- ✅ 需要 Memory（记住已问过的问题）

**提问策略**：
- 优先问关键信息
- 避免重复提问
- 提供选项而非开放式问题

---

## 四、Tool 设计

### 4.1 Tool 基类

```python
class Tool:
    """工具基类"""
    name: str
    description: str
    parameters: dict  # JSON Schema
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass
```

### 4.2 工具清单

#### 4.2.1 文件处理工具

| 工具 | 功能 | Agent |
|------|------|-------|
| `file_parser` | 解析 PDF/DOCX/TXT | JD Analyzer, Profile Extractor |
| `text_cleaner` | 清理文本格式 | JD Analyzer |
| `html_renderer` | 渲染 HTML 简历 | Render Agent |

#### 4.2.2 信息提取工具

| 工具 | 功能 | Agent |
|------|------|-------|
| `entity_extractor` | 提取实体（姓名、公司、技能） | Profile Extractor |
| `keyword_extractor` | 提取关键词 | JD Analyzer |
| `date_parser` | 解析日期 | Profile Extractor |

#### 4.2.3 内容生成工具

| 工具 | 功能 | Agent |
|------|------|-------|
| `template_search` | 搜索简历模板 | Content Generator |
| `best_practices` | 查询最佳实践 | Content Generator |
| `keyword_optimizer` | 优化关键词 | Content Generator |

#### 4.2.4 知识检索工具（RAG）

| 工具 | 功能 | Agent |
|------|------|-------|
| `question_bank` | 搜索面试题库 | Interview QA |
| `industry_standards` | 查询行业标准 | Gap Analyzer |
| `similar_cases` | 参考类似案例 | Gap Analyzer, Content Generator |

#### 4.2.5 状态管理工具

| 工具 | 功能 | Agent |
|------|------|-------|
| `state_reader` | 读取会话状态 | 所有 Agent |
| `state_writer` | 写入会话状态 | 所有 Agent |

### 4.3 工具实现示例

```python
class FileParserTool(Tool):
    """文件解析工具"""
    name = "file_parser"
    description = "解析 PDF/DOCX/TXT 文件，提取文本内容"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "文件路径"},
            "file_type": {"type": "string", "enum": ["pdf", "docx", "txt"]}
        },
        "required": ["file_path", "file_type"]
    }
    
    async def execute(self, file_path: str, file_type: str) -> ToolResult:
        if file_type == "pdf":
            text = await self.parse_pdf(file_path)
        elif file_type == "docx":
            text = await self.parse_docx(file_path)
        else:
            text = await self.parse_txt(file_path)
        
        return ToolResult(success=True, data={"text": text})
```

---

## 五、Memory 设计

### 5.1 Memory 架构

```
┌─────────────────────────────────────────────────────────┐
│                    Memory System                         │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Short-term Memory                   │   │
│  │  - 当前对话历史                                  │   │
│  │  - 最近 10 轮消息                                │   │
│  │  - 存储在 Redis                                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Working Memory                      │   │
│  │  - 当前任务上下文                                │   │
│  │  - Agent 间共享数据                              │   │
│  │  - 存储在 GraphState                             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Long-term Memory                    │   │
│  │  - 用户偏好                                      │   │
│  │  - 历史简历                                      │   │
│  │  - 学习记录                                      │   │
│  │  - 存储在 MySQL + 向量数据库                     │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Memory 类型

#### 5.2.1 Short-term Memory（短期记忆）

**存储内容**：
- 当前对话历史
- 最近 10 轮消息
- 当前会话上下文

**实现**：
```python
class ShortTermMemory:
    """短期记忆 - 对话历史"""
    
    def __init__(self, redis_client, session_id: str):
        self.redis = redis_client
        self.session_id = session_id
        self.max_messages = 20  # 最多 20 条消息
    
    async def add_message(self, message: dict):
        """添加消息"""
        await self.redis.lpush(f"session:{self.session_id}:messages", 
                               json.dumps(message))
        await self.redis.ltrim(f"session:{self.session_id}:messages", 
                               0, self.max_messages - 1)
    
    async def get_messages(self, limit: int = 10) -> list[dict]:
        """获取最近消息"""
        messages = await self.redis.lrange(
            f"session:{self.session_id}:messages", 0, limit - 1
        )
        return [json.loads(m) for m in messages]
```

#### 5.2.2 Working Memory（工作记忆）

**存储内容**：
- 当前任务上下文
- Agent 间共享数据
- 临时计算结果

**实现**：
```python
class WorkingMemory:
    """工作记忆 - 任务上下文"""
    
    def __init__(self):
        self.data = {}
    
    def get(self, key: str, default=None):
        return self.data.get(key, default)
    
    def set(self, key: str, value):
        self.data[key] = value
    
    def update(self, data: dict):
        self.data.update(data)
    
    def clear(self):
        self.data.clear()
```

#### 5.2.3 Long-term Memory（长期记忆）

**存储内容**：
- 用户偏好（简历风格、求职意向）
- 历史简历版本
- 学习记录（哪些修改被采纳）

**实现**：
```python
class LongTermMemory:
    """长期记忆 - 用户偏好和历史"""
    
    def __init__(self, mysql_client, user_id: str):
        self.mysql = mysql_client
        self.user_id = user_id
    
    async def get_preferences(self) -> dict:
        """获取用户偏好"""
        return await self.mysql.query(
            "SELECT * FROM user_preferences WHERE user_id = %s",
            (self.user_id,)
        )
    
    async def save_preference(self, key: str, value):
        """保存用户偏好"""
        await self.mysql.upsert(
            "user_preferences",
            {"user_id": self.user_id, "key": key, "value": json.dumps(value)}
        )
    
    async def get_resume_history(self) -> list[dict]:
        """获取简历历史版本"""
        return await self.mysql.query(
            "SELECT * FROM resume_versions WHERE user_id = %s ORDER BY created_at DESC",
            (self.user_id,)
        )
```

### 5.3 Memory 使用场景

| 场景 | Memory 类型 | 示例 |
|------|-------------|------|
| 用户说"用我之前的风格" | Long-term | 查询用户偏好 |
| Agent 问"你有什么项目经验？" | Short-term | 记住已问过的问题 |
| Content Generator 生成简历 | Working | 存储中间结果 |
| 用户说"上次的简历更好" | Long-term | 查询历史版本 |

---

## 六、Reflection 设计

### 6.1 Reflection 机制

**何时需要 Reflection**：
- Content Generator 生成简历后
- Interview QA 生成面试题后
- Render Agent 渲染 HTML 后

**Reflection 流程**：
```
┌─────────────────────────────────────────────────────┐
│                    Reflection Flow                    │
│                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │ Generate │───▶│ Evaluate│───▶│ Decide  │         │
│  └─────────┘    └─────────┘    └─────────┘         │
│                                    │                 │
│                                    ▼                 │
│                           ┌─────────────┐            │
│                           │ quality >=  │            │
│                           │   0.8 ?     │            │
│                           └─────────────┘            │
│                              │        │              │
│                              ▼        ▼              │
│                          ┌─────┐  ┌─────┐            │
│                          │ Yes │  │ No  │            │
│                          └─────┘  └─────┘            │
│                            │        │                │
│                            ▼        ▼                │
│                         ┌─────┐  ┌─────┐             │
│                         │ END │  │Revise│             │
│                         └─────┘  └─────┘             │
└─────────────────────────────────────────────────────┘
```

### 6.2 评估维度

```python
class ReflectionResult:
    """反思结果"""
    quality_score: float  # 0-1
    dimensions: dict[str, float]  # 各维度分数
    issues: list[str]  # 发现的问题
    suggestions: list[str]  # 改进建议
    should_revise: bool  # 是否需要修正
```

**评估维度**：

| 维度 | 权重 | 说明 |
|------|------|------|
| 完整性 | 0.25 | 是否覆盖所有要求 |
| 准确性 | 0.25 | 信息是否准确 |
| 专业性 | 0.20 | 用词是否专业 |
| 一致性 | 0.15 | 各部分是否一致 |
| 可读性 | 0.15 | 排版是否清晰 |

### 6.3 Reflection 实现

```python
class ReflectionEngine:
    """反思引擎"""
    
    async def evaluate(self, content: dict, context: dict) -> ReflectionResult:
        """评估内容质量"""
        
        # 1. 完整性检查
        completeness = await self.check_completeness(content, context)
        
        # 2. 准确性检查
        accuracy = await self.check_accuracy(content, context)
        
        # 3. 专业性检查
        professionalism = await self.check_professionalism(content)
        
        # 4. 一致性检查
        consistency = await self.check_consistency(content)
        
        # 5. 可读性检查
        readability = await self.check_readability(content)
        
        # 计算总分
        total_score = (
            completeness * 0.25 +
            accuracy * 0.25 +
            professionalism * 0.20 +
            consistency * 0.15 +
            readability * 0.15
        )
        
        # 生成改进建议
        suggestions = await self.generate_suggestions(content, {
            "completeness": completeness,
            "accuracy": accuracy,
            "professionalism": professionalism,
            "consistency": consistency,
            "readability": readability
        })
        
        return ReflectionResult(
            quality_score=total_score,
            dimensions={...},
            issues=[...],
            suggestions=suggestions,
            should_revise=total_score < 0.8
        )
```

---

## 七、Multi-Agent 协作

### 7.1 协作模式

#### 模式 1：顺序协作（Pipeline）

```
Planner → JD Analyzer → Gap Analyzer → Content Generator → Render Agent
```

**适用场景**：标准流程，一个 Agent 的输出是下一个的输入

#### 模式 2：并行协作（Fan-out）

```
                ┌─ Profile Extractor ─┐
Planner ────────┤                     ├──── Content Generator
                └─ Gap Analyzer ──────┘
```

**适用场景**：多个 Agent 可以同时执行

#### 模式 3：请求协作（Request）

```
Content Generator ──request──▶ Gap Analyzer
      │
      └──response──▶ 继续生成
```

**适用场景**：Agent 需要其他 Agent 的帮助

### 7.2 协作实现

```python
class CollaborativeAgent(BaseAgent):
    """支持协作的 Agent"""
    
    async def request_help(self, agent_name: str, question: str) -> dict:
        """请求其他 Agent 帮助"""
        # 1. 暂停当前执行
        # 2. 调用目标 Agent
        # 3. 获取结果
        # 4. 继续执行
        
        other_agent = self.agent_pool.get(agent_name)
        result = await other_agent.execute(
            self.state.update({"help_request": question})
        )
        return result
```

### 7.3 协作场景

| 场景 | 协作方式 | 说明 |
|------|----------|------|
| Content Generator 需要 Gap 分析 | 请求协作 | 查询差距分析结果 |
| Interview QA 需要 JD 信息 | 请求协作 | 查询职位要求 |
| Reviewer 需要原始 JD | 请求协作 | 对比审查 |
| Profile + Gap 并行执行 | 并行协作 | 同时提取画像和分析差距 |

---

## 八、LangGraph 集成

### 8.1 GraphState 设计

```python
class GraphState(TypedDict):
    """LangGraph 图状态"""
    
    # 会话信息
    session_id: str
    user_id: str
    
    # 用户输入
    user_message: str
    user_attachments: list[dict]
    
    # 业务数据
    jd_text: str
    jd_analysis: dict
    profile: dict
    gap_analysis: dict
    resume_content: dict
    resume_html: str
    render_config: dict
    interview_qa: list[dict]
    
    # 流程控制
    stage: str  # init, has_jd, has_profile, has_resume, completed
    current_agent: str
    execution_plan: list[str]
    
    # Memory
    conversation_history: Annotated[list[dict], operator.add]
    working_memory: dict
    user_preferences: dict
    
    # Reflection
    reflection_result: dict
    quality_score: float
    iterations: int
    
    # 输出
    reply_message: str
    workflow_trace: list[dict]
```

### 8.2 Graph 结构

```python
def build_graph() -> StateGraph:
    """构建 LangGraph 图"""
    graph = StateGraph(GraphState)
    
    # 添加节点
    graph.add_node("planner", planner_node)
    graph.add_node("jd_analyzer", jd_analyzer_node)
    graph.add_node("profile_extractor", profile_extractor_node)
    graph.add_node("gap_analyzer", gap_analyzer_node)
    graph.add_node("content_generator", content_generator_node)  # 带循环
    graph.add_node("render_agent", render_agent_node)
    graph.add_node("interview_qa", interview_qa_node)  # 带循环
    graph.add_node("reviewer", reviewer_node)  # 带循环
    graph.add_node("clarifier", clarifier_node)
    
    # 设置入口
    graph.set_entry_point("planner")
    
    # Planner 条件路由
    graph.add_conditional_edges("planner", route_after_planner, {
        "jd_analyzer": "jd_analyzer",
        "profile_extractor": "profile_extractor",
        "gap_analyzer": "gap_analyzer",
        "content_generator": "content_generator",
        "render_agent": "render_agent",
        "interview_qa": "interview_qa",
        "clarifier": "clarifier",
        "respond": "respond"
    })
    
    # JD Analyzer → Gap Analyzer 或 Content Generator
    graph.add_conditional_edges("jd_analyzer", route_after_jd, {
        "gap_analyzer": "gap_analyzer",
        "content_generator": "content_generator",
        "respond": "respond"
    })
    
    # Gap Analyzer → Content Generator
    graph.add_edge("gap_analyzer", "content_generator")
    
    # Content Generator → Reviewer（循环）
    graph.add_conditional_edges("content_generator", route_after_content, {
        "reviewer": "reviewer",  # 需要审查
        "render_agent": "render_agent",  # 直接渲染
        "respond": "respond"
    })
    
    # Reviewer → Content Generator（循环）或 Render Agent
    graph.add_conditional_edges("reviewer", route_after_review, {
        "content_generator": "content_generator",  # 需要修正
        "render_agent": "render_agent",  # 审查通过
        "respond": "respond"
    })
    
    # Render Agent → Interview QA
    graph.add_edge("render_agent", "interview_qa")
    
    # Interview QA → END
    graph.add_edge("interview_qa", "respond")
    
    # Respond → END
    graph.add_edge("respond", END)
    
    return graph
```

### 8.3 循环控制

```python
async def content_generator_node(state: GraphState) -> dict:
    """Content Generator 节点（带循环）"""
    
    max_iterations = 3
    quality_threshold = 0.8
    
    for iteration in range(max_iterations):
        # 1. 生成内容
        content = await generate_content(state)
        
        # 2. 反思评估
        reflection = await reflection_engine.evaluate(content, state)
        
        # 3. 更新状态
        state.update({
            "resume_content": content,
            "reflection_result": reflection,
            "quality_score": reflection.quality_score,
            "iterations": iteration + 1
        })
        
        # 4. 判断是否继续
        if reflection.quality_score >= quality_threshold:
            break
        
        if not reflection.should_revise:
            break
    
    return state
```

---

## 九、实施计划

### 9.1 Phase 5 调整

**原计划**：实现 7 个 Agent（简单版）

**新计划**：实现 9 个 Agent（完整版）

| Agent | 原设计 | 新设计 | 改动 |
|-------|--------|--------|------|
| Planner | 路由器 | 路由器 + 状态感知 | 小改 |
| JD Analyzer | 提取器 | 提取器 + 工具 | 中改 |
| Profile Extractor | 提取器 | 提取器 + 工具 | 中改 |
| Gap Analyzer | 提取器 | 提取器 + 工具 + RAG | 中改 |
| Content Generator | 生成器 | 生成器 + 循环 + Reflection | 大改 |
| Render Agent | 生成器 | 生成器 + 循环 | 中改 |
| Interview QA | 生成器 | 生成器 + 循环 + RAG | 大改 |
| Reviewer | 无 | 新增 | 新增 |
| Clarifier | 无 | 新增 | 新增 |

### 9.2 Phase 6 调整

**原计划**：简单 LangGraph 图

**新计划**：完整 LangGraph 图 + 循环 + 协作

### 9.3 新增 Phase

**Phase 5.5：Tool + Memory 实现**
- 实现 Tool 基类
- 实现 5 个核心工具
- 实现 Memory 系统

**Phase 6.5：Reflection + RAG 实现**
- 实现 Reflection 引擎
- 实现 RAG 检索
- 集成到 Agent 中

---

## 十、总结

### 10.1 设计亮点

1. **实用主义**：不为了 Agent 而 Agent，简单任务用简单方案
2. **分层设计**：Router / Extractor / Generator 三类 Agent
3. **渐进增强**：先跑通核心流程，再添加高级功能
4. **真正循环**：只有需要循环的 Agent 才有循环
5. **Memory 三层**：短期 / 工作 / 长期，各司其职

### 10.2 与原设计对比

| 维度 | 原设计 | 新设计 |
|------|--------|--------|
| Agent 类型 | 7 个（同质化） | 9 个（分类） |
| 循环机制 | 无 | 有（关键 Agent） |
| Tool Use | 无 | 有（5+ 工具） |
| Memory | 无 | 有（三层） |
| Reflection | 无 | 有（多维度） |
| 协作 | 无 | 有（三种模式） |

### 10.3 风险提示

1. **复杂度增加**：新设计更复杂，需要更多测试
2. **性能影响**：循环和 Reflection 会增加延迟
3. **成本增加**：更多 LLM 调用意味着更高成本

### 10.4 建议

1. **分阶段实施**：先实现核心功能，再添加高级功能
2. **充分测试**：每个 Agent 都需要单元测试和集成测试
3. **性能监控**：监控延迟和成本，及时优化
4. **用户反馈**：收集用户反馈，迭代改进

---

**设计完成，等待评审。**
