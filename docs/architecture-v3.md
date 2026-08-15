# CareerAssistant 架构改造设计 v3 — Agent 基础能力 + 求职全流程

> **文档类型**: 架构设计文档（Architecture Design）
> **状态**: 待评审
> **日期**: 2026-08-15
> **范围**: 主流程改造（意图分类 / 增量编辑 / 三大基础能力）+ 求职信生成器；AI 模拟面试仅预留接口
> **参考**: [architecture-v2.md](./architecture-v2.md)（v2 原始设计）、ai-career-copilot（参考项目，见第十一章）

---

## 1. 背景与目标

### 1.1 问题陈述

当前系统是"固定流水线"：`规则路由 → JD 分析 → 画像提取 → 差距分析 → 简历生成 → 评审 → 渲染 → 面试题`。用户感受"鸡肋"——同样的输入贴给任意对话 AI 也能得到相似结果。代码事实层面的根因：

| # | 问题 | 代码事实 |
|---|------|---------|
| 1 | **无意图理解** | `graph/edges.py` 的 `rule_based_route` 是纯 if/else 状态判断，无法识别"改简历 / 换岗位 / 自由提问 / 生成求职信"等意图 |
| 2 | **换岗位/补经历不生效（bug）** | 路由只看"字段存不存在"（`need_jd = has_jd_text and not has_jd`），上传新 JD 时 `has_jd=True` → 旧分析不重跑，下游全部停留在旧岗位 |
| 3 | **画像提取会覆盖旧数据** | `profile_extractor` 每次全量提取，补材料会丢已有信息 |
| 4 | **无跨会话记忆** | 会话间完全隔离；`user_preferences` 表存在但无任何 Agent 读取 |
| 5 | **错误处理不完整** | 有重试/超时/SSE error，但无节点级失败记录、无 LLM 输出 schema 校验、无错误分类体系 |
| 6 | **工具未契约化** | 工具已接线（gap/interview/content），但无统一契约文档，新增工具依赖人肉记忆 |
| 7 | **无自由问答** | 用户只能"跑流程"，不能基于当前分析结果提问 |

### 1.2 目标

1. **主流程达到参考项目成熟度**：LLM 意图分类（规则引擎降为 guardrail）、增量编辑（换岗位/补经历跟着变）、执行过程用户可见（intent + trace）
2. **补齐 Agent 项目三大基础**：Memory 管理机制、错误处理体系、工具调用契约
3. **新增功能点**：求职信 / 招聘软件打招呼生成器
4. **为后续预留**：AI 模拟面试（语音，M4 里程碑，本期只留接口与数据位）

---

## 2. 目标架构总览

```
用户输入
  ↓
意图分类层（LLM，FAST_MODEL）── 失败/低置信时回退规则引擎（guardrail）
  ↓ intent ∈ {upload_jd, upload_profile, gap_analysis, content_edit,
  │           render_edit, export, ask_question, generate_cover_letter}
  ↓
能力单元编排（LangGraph 现有图扩展，按 intent 选链 + 增量检测裁剪）
  ├─ 求职引擎：jd / profile / gap / content / review / render / interview（现有）
  ├─ 问答单元：question（新增，只读状态回答）
  └─ 求职信单元：cover_letter（新增，生成类）
  ↓
执行过程（流式）：progress + intent + 各产物事件（现有 SSE 扩展）
  ↓
会话结束
  ↓
记忆维护（consolidate 节点，LLM 一步）── 增量合并进 career_profile（跨会话）
```

**设计原则**（延续 v2 的"实用优先"）：
- 不新增"独立 Agent 实体"，新增的只是**能力单元**（LLM 调用点）+ **一个记忆维护节点**
- 多 Agent 的价值体现在"意图识别 + 增量编排 + 记忆"的联动，而非拆更多流水线工人
- 所有 LLM 输出经确定性代码校验后再落库

---

## 3. 详细设计

### 3.1 意图分类与路由

**方案**：恢复 LLM 意图分类（参考项目 `intent_classification.py` 模式），规则引擎降为 guardrail。

**意图集合**：

| intent | 触发示例 | 执行链 |
|--------|---------|--------|
| `upload_jd` | 粘贴/上传 JD | jd → gap → content → review → render → interview（按增量裁剪） |
| `upload_profile` | 上传简历/补材料 | profile（增量合并）→ gap → content → review → render → interview |
| `gap_analysis` | "分析下匹配度" | gap |
| `content_edit` | "把项目经历写得更突出" | content（局部 section 更新）→ render |
| `render_edit` | "行距宽一点 / 换模板" | render（只改 render_config） |
| `export` | "导出 PDF" | 导出服务（非 LLM） |
| `ask_question` | "这岗位我匹配吗 / 简历里有什么" | question（只读） |
| `generate_cover_letter` | "帮我写个求职信 / 打招呼文案" | cover_letter |
| `fallback`（规则引擎兜底） | LLM 解析失败/低置信 | 现 `rule_based_route` |

**实现要点**：
- 新增 `backend/app/prompts/intent_classification.py`（独立 prompt，参考项目风格：状态摘要 + 用户消息 + JSON 协议）
- 新增 `backend/app/graph/intent.py`：`classify_intent(state) -> {intent, reason, confidence}`，调 FAST_MODEL 一次
- `planner_node`：先 LLM 分类；解析失败或 confidence 低 → 回退 `rule_based_route`（现有逻辑保留）
- 路由表按 intent 驱动，但**仍经过增量检测裁剪**（见 3.2）
- 并行/评审/流式等现有能力全部保留

**配置**：`prompts/` 目录结构参考项目（prompt 与代码分离，便于调优）。

### 3.2 增量编辑（换岗位/补经历"跟着变"）

**核心：从"字段存不存在"升级为"输入变没变"**

**3.2.1 输入变化检测**

- `GraphState` 新增：`jd_input_hash: str`、`resume_input_hash: str`
- 会话（Redis）持久化这两个哈希
- `send_message` 时计算新输入摘要（`sha256(规范化文本)`）：
  - 新 JD 文本哈希 ≠ 会话中哈希 → 强制重跑 jd_analyzer（**无视 `has_jd`**），并级联重算下游
  - 新简历材料哈希 ≠ 会话中哈希 → 强制重跑 profile_extractor，级联重算下游
  - 都相等 → 走现有"补跑缺失步骤"逻辑
- 文本规范化：去空白/大小写后取哈希，避免"仅格式变化"误触发重跑

**3.2.2 级联重算规则**

| 变化 | 重算 | 保留 |
|------|------|------|
| JD 变了 | jd → gap → content → interview（review 随 content） | render_config（模板/字号不动） |
| Profile 变了 | profile → gap → content → interview（review 随 content） | render_config |
| 只有 render_edit | 仅 render | 内容全部保留 |
| 无变化 | 现有补跑逻辑 | — |

**3.2.3 Profile 增量合并**

- `profile_extractor` 增加合并模式：输入 = `existing_profile + 新材料`，prompt 指示"将新材料合并进已有画像：补充新经历/技能，修正冲突信息，**不删除、不覆盖**已有内容"
- 合并结果经规则校验（新字段不为空、experience 不丢失）后落库

**3.2.4 与现有流程的关系**

- `rule_based_route` 保留（guardrail + 无意图场景）
- `parallel_analysis` / `parallel_post` / 评审循环 / 即时持久化全部保留

### 3.3 Memory 管理机制（三大基础之一）

**分层设计**：

```
┌─ 会话内记忆（已有，补齐）─────────────────────────┐
│  GraphState 工作记忆 ✓                            │
│  messages + conversation_history 注入（Clarifier）✓ │
│  clarification_history（多轮澄清）✓                │
└──────────────────────────────────────────────────┘
┌─ 跨会话长期记忆（本期新增 MVP）───────────────────┐
│  career_profile：长期求职档案（技能/经历/偏好/缺口） │
│  user_preferences：用户偏好（表已存在，接入）       │
└──────────────────────────────────────────────────┘
┌─ 记忆维护（一个 LLM 节点，非 Agent）──────────────┐
│  consolidate_memory：会话增量 → 档案变更建议       │
│  （add/update/conflict 标记）→ 代码校验后落库      │
└──────────────────────────────────────────────────┘
```

**3.3.1 数据模型（M1 新增 1 张表）**

```sql
CREATE TABLE career_profiles (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,                 -- 关联 users（若未登录则归匿名桶）
  profile_json  JSON NOT NULL,                -- 长期画像（技能/经历/偏好/缺口）
  source        VARCHAR(32) DEFAULT 'resume', -- resume / consolidate
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_user (user_id)
);
```

- `user_preferences` 表已存在，本期接入（读：会话开始时注入；写：用户明确设置时）
- M3 扩展：`job_applications`（投递记录）、`interview_logs`（面试记录，含模拟面试）

**3.3.2 读写时机**

| 时机 | 动作 | 实现 |
|------|------|------|
| 会话开始（用户已登录） | 注入 career_profile 摘要 + user_preferences 到 graph_state | API 层读取，`memory_summary` 字段 |
| 上传简历且 profile_extractor 完成 | 规则化合并：新技能/经历 append（去重） | `MemoryRepository.upsert`（纯代码） |
| 会话结束 | 若本轮有"值得提炼的增量"，调 consolidate | 见 3.3.3 |
| 用户明确说"记住我的偏好" | 写入 user_preferences | Clarifier/能力单元输出结构化偏好 |

**3.3.3 consolidate_memory 节点（LLM 一步）**

- **触发条件**：本轮有新增材料/明确反馈（由规则判断：有 upload_profile、content_edit、显式偏好语句），避免每轮白调用
- **输入**：本轮对话摘要 + 现有 career_profile 摘要
- **输出（JSON schema）**：
  ```json
  {"updates": [
     {"op": "add|update", "field": "skills|experience|preferences|gaps", "value": "...", "reason": "..."},
     {"op": "conflict", "field": "...", "old": "...", "new": "..."}
  ]}
  ```
- **落库前代码校验**：只允许白名单字段、拒绝空值、conflict 项人工（对话中）确认，防止 LLM 乱写

### 3.4 错误处理体系（三大基础之二）

**现状盘点**（已有）：错误类型感知重试（429/5xx 重试、401/400 快失败）、单 Agent 超时 120s、整图超时 GRAPH_TIMEOUT、SSE error 事件（带 hint）、并行节点 return_exceptions、会话并发锁、中断时即时持久化。

**本期补齐**：

| # | 能力 | 设计 |
|---|------|------|
| 1 | **节点级失败记录** | `workflow_trace`：每个能力单元执行后记录 `{node, status, input_summary, output_summary, error, latency_ms}`（参考项目 trace.py）；失败节点仍继续推进（部分成功） |
| 2 | **LLM 输出 schema 校验** | 新增 `ainvoke_json_with_schema`（参考项目 `models/llm.py`）：Pydantic schema + 解析失败自动重试 1 次 + 仍失败走 fallback 结构 |
| 3 | **错误分类与用户提示映射** | 错误 → 分类（文件解析/超时/网络/JSON 格式/意图不明）→ 统一 hint 文案（现 error_hint 逻辑扩展为分类表） |
| 4 | **失败原因进 trace** | 前端可通过 SSE 展示"哪一步失败、为什么、建议怎么做" |
| 5 | **幂等与重试策略** | 会话锁已有；能力单元保持幂等（同输入同输出，render 已具备） |

### 3.5 工具调用契约（三大基础之三）

**现状**：`BaseAgent` tool-calling 循环（上限 5 轮）；已接线：`gap_analyzer`（similar_cases/RAG）、`interview_qa`（question_bank）、`content_generator`（best_practices/keyword_optimizer/template_search）。

**本期补充**：

1. **工具契约文档**（`docs/agents-contract.md`，参考项目契约思想落地）：
   | 工具 | 输入 | 输出 | 绑定能力单元 | 失败降级 |
   |------|------|------|-------------|---------|
   | similar_cases (RAG) | query/category | 案例列表 | gap | 返回空，继续分析 |
   | question_bank | category/topic/... | 题目列表 | interview | 返回空，LLM 自生成 |
   | best_practices | topic | 最佳实践 | content / **cover_letter** | 返回空，LLM 直接生成 |
   | keyword_optimizer | resume_kw/jd_kw | 覆盖率+建议 | content | 返回空 |
   | template_search | style | 模板列表 | content / cover_letter | 返回默认模板 |
2. **新增工具**（cover_letter 用）：`company_lookup`（公司背景查询，Firecrawl/静态库，M2 可选）
3. 工具调用结果进入 workflow_trace（用了什么工具、结果摘要），便于排查

### 3.6 自由问答（question 能力单元）

- 意图 `ask_question` → `question` 节点：基于**当前 graph_state 摘要**回答（参考项目 `question_agent.py`：排除 HTML/trace 等大字段，压缩后注入 prompt）
- **只读**：不写任何业务状态，仅写 workflow_trace
- 信息不足时明确告知"缺什么数据、下一步补什么"

### 3.7 求职信 / 打招呼生成器（新功能点）

**能力单元**：`cover_letter_agent`（生成类，主模型）

- **输入**：profile（压缩）+ jd_analysis（压缩）+ gap_analysis（压缩）+ `channel`（`linkedin_message` 招聘软件打招呼 / `email` 正式求职信）+ 用户指令
- **输出**：
  ```json
  {"channel": "email|linkedin_message", "subject": "主题（email 用）",
   "body": "正文", "tone": "professional|friendly", "highlights": ["引用点1", ...]}
  ```
- **工具**：best_practices（写作要点）、template_search（模板风格，可选）
- **Prompt 要点**：打招呼 < 100 字、突出与 JD 的匹配点、引用具体经历（不捏造）；求职信 150-300 字结构（开场→匹配点→价值→行动号召）
- **路由**：intent `generate_cover_letter`；SSE 新事件 `cover_letter`
- **前端**：ResultPanel 新增 tab 或 ChatPanel 卡片展示；历史存入 session（复用持久化机制）

### 3.8 执行过程用户可见（trace 落地）

- SSE 新增事件：`intent`（`{intent, reason, plan[]}`）、`trace`（`{node, status, summary}`，节点完成后推送）
- 前端：ChatPanel 展示"识别到意图 X → 计划：A → B → C"，进度行复用现有 progress 机制
- 现有 progress + 各产物事件全部保留

---

## 4. 接口设计

### 4.1 API

| 方法 | 路径 | 说明 | 变更 |
|------|------|------|------|
| POST | /api/sessions/ | 创建会话 | 无 |
| GET | /api/sessions/ | 历史列表 | 无（已上线） |
| POST | /api/sessions/{id}/messages | SSE 消息 | 内部：意图分类、增量检测 |
| GET | /api/sessions/{id} | 会话详情 | 返回新增字段（jd_input_hash 等可选） |
| POST | /api/sessions/{id}/upload | 上传 | 无 |

### 4.2 SSE 事件扩展

| 事件 | 载荷 | 阶段 |
|------|------|------|
| `start` | 处理中 | 现有 |
| `progress` | 节点进度 | 现有 |
| **`intent`** | `{intent, reason, plan[]}` | M1 |
| **`trace`** | `{node, status, summary}` | M1 |
| `jd_analysis/profile/gap_analysis/resume_content/render_config/interview_questions` | 产物 | 现有 |
| **`cover_letter`** | `{channel, subject, body, ...}` | M2 |
| `clarification` | 追问 | 现有 |
| `done` / `error` | 完成/失败 | 现有（error 扩展 hint 分类） |

---

## 5. 数据模型（本期新增汇总）

| 表 | 用途 | 里程碑 |
|----|------|--------|
| `career_profiles` | 长期求职档案 | M1 |
| `user_preferences` | 用户偏好（表已存在，接入） | M1 |
| `cover_letters` | 求职信历史（可选） | M2 |
| `job_applications` / `interview_logs` | 投递/面试记录（长久陪伴） | M3 |
| `plan_runs` / `step_runs` | 执行轨迹持久化（可选，先内存 trace） | M3 |

---

## 6. 实施里程碑

> 原则：每期可独立验收、不破坏现有功能；先主流程后扩展；模拟面试只预留。

### M1 — 主流程达标 + 三大基础（核心交付）✅ 已完成（2026-08-15）

1. ✅ **意图分类**：prompts/intent_classification.py + graph/intent.py + planner 接入（规则引擎降 guardrail）
2. ✅ **增量编辑**：输入版本检测（jd/profile_input_version + 下游基于版本）+ 级联重算 + profile 增量合并（修复"换岗位不重跑"bug）
3. ✅ **错误处理**：trace 节点记录 + `llm/structured.py` schema 校验（自动重试）+ `_classify_error` 错误分类 hint（error 事件带 category）
4. ✅ **Memory MVP**：career_profiles 表 + MemoryService 规则合并 + create_session 用户绑定 + memory_summary 注入 + **consolidate 提炼节点**（LLM 一步，schema 校验 + 白名单落库）
5. ✅ **工具契约**：docs/agents-contract.md
6. ✅ **SSE 扩展**：intent + trace + answer + cover_letter 事件；前端展示

**验收结果**：
- 换岗位（JD 输入版本 +1）→ jd/gap/content/interview 级联重算 ✅
- 输入未变 → 不重跑 ✅
- 意图分类失败 → 规则引擎兜底 ✅（test_intent.py 8 项）
- 跨会话：简历上传后 career_profile 规则合并 ✅（test_memory_service.py 10 项）
- 284 个测试全绿

### M2 — 功能扩展（已完成）

1. ✅ **求职信生成器**：cover_letter_agent 双渠道（email/linkedin_message），用户先选渠道（Clarifier 追问）
2. ✅ **自由问答**：question 能力单元（只读）
3. ✅ 错误分类 hint 扩展（_classify_error）
4. ✅ **简历导出**：POST /api/sessions/{id}/export（html/json/md）+ 前端导出按钮（按用户要求补充）

### M2.5 — 记忆提炼（补全）

- ✅ `consolidate` 提炼节点：LLM 一步（`ainvoke_json_with_schema`）+ 字段白名单 + 空值过滤 + 落库；upload_profile / content_edit 意图后触发（sessions.py）
- ✅ `llm/structured.py`：`ainvoke_json_with_schema`（schema 校验 + 自动重试 1 次），供新能力单元使用

### M3 — 长久陪伴（待推进）

1. `job_applications` / `interview_logs` 表 + 对话式记录（复用 Clarifier 追问）
2. 面试失败 → 教训提取 → 技能缺口更新 → 下次面试前提醒
3. plan_runs/step_runs 持久化

### M4 — AI 模拟面试（预留，不实施）

- **预留点**：`interview_logs` 表设计（真实/模拟统一建模）、question_bank 扩展、语音输入输出接口位
- **明确不做**：本期不引入语音模型、不实现模拟面试对话循环

---

## 7. 测试策略

| 层 | 内容 |
|----|------|
| 能力单元 | 每个 Agent 的 build_messages/parse_response 单测（MockLLM，已有模式） |
| 意图分类 | 各 intent 命中/兜底/解析失败（MockLLM 返回不同 JSON） |
| 增量编辑 | 哈希变化→重跑、哈希不变→跳过、profile 合并不丢旧数据（集成测试） |
| Memory | consolidate 输出 schema 校验、非法字段拒绝、落库幂等 |
| SSE | 事件顺序与载荷（extend test_api 现有模式） |
| 回归 | 现有 257 测试保持全绿 |

---

## 8. 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 意图分类不稳定（多花一次调用 + 误判） | 用 FAST_MODEL（成本低）；规则引擎 guardrail 兜底；confidence 低回退 |
| 增量哈希误判（规范化不足导致误重跑/漏重跑） | 文本规范化后取哈希；测试覆盖格式变化场景 |
| 记忆污染（LLM 提炼乱写档案） | 白名单字段 + 空值拒绝 + conflict 需确认 + 代码校验兜底 |
| 改动面大回归 | 分里程碑；每期跑全量 257 测试 + 新增用例 |
| 参考项目"固定链路"教训 | 我们不照抄固定链路；意图路由仍经过增量检测与现有动态图 |

---

## 9. 与参考项目（ai-career-copilot）的对照

| 能力 | 参考项目 | 本方案 |
|------|---------|--------|
| LLM 意图分类 | ✅ 7 类 | ✅ 8 类（+generate_cover_letter），规则引擎兜底 |
| 增量编辑 | ✅ dirty flags（设计） | ✅ 输入哈希 + 级联重算（修掉现有 bug） |
| 自由问答 | ✅ question_agent | ✅ question 能力单元 |
| workflow_trace | ✅ | ✅（结合我们的流式，边跑边推） |
| Agent 契约 | ✅ 文档 | ✅ docs/agents-contract.md + 工具契约 |
| 工具调用 | ❌ | ✅（我们已有，保留强化） |
| 评审迭代 | ❌ | ✅（我们已有，保留） |
| 流式推送 | ❌ 一次性 | ✅（我们已有，保留） |
| 长期记忆 | ❌ 会话内 | ✅ career_profile + consolidate（本期新增） |
| 求职信生成 | ❌ | ✅（本期新增） |

---

## 10. 文档维护说明

- 本文档是**设计基线**，随实施按里程碑更新（每完成一个 M 里程碑，在对应章节标注 ✅）
- 实施过程中的偏差（如意图集合调整）需同步修订本文档与 `docs/agents-contract.md`
- 相关文档索引见 `docs/README.md`
