# AI 模拟面试 — 开发参考文档

> 精简版，供开发时查阅。设计分析见 git history。

---

## 模块划分

```
backend/app/
├── voice/                          # 语音层（WebSocket + ASR + TTS）
│   ├── gateway.py                  # WebSocket 路由 + 双 Task 架构
│   ├── asr_service.py              # MiMo ASR（复用参考项目调用方式）
│   ├── tts_service.py              # MiMo TTS（复用参考项目调用方式）
│   ├── audio_utils.py              # PCM↔WAV 转换
│   ├── protocol.py                 # 消息类型定义
│   └── interview_handler.py        # Voice↔Interview 桥接
│
├── interview/                      # 模拟面试核心
│   ├── state.py                    # InterviewState
│   ├── graph.py                    # LangGraph 子图
│   ├── nodes.py                    # 图节点
│   ├── edges.py                    # 条件路由
│   ├── session_service.py          # 持久化（复用 SessionStore 接口）
│   └── report.py                   # 面试报告生成
│
├── agents/
│   ├── interviewer.py              # 生成提问/追问（继承 BaseAgent）
│   └── evaluator.py                # 评价+决策（继承 BaseAgent）
│
├── api/interview.py                # REST API（创建/查询/报告）
└── models/schemas.py               # 扩展 InterviewTurn, EvaluationDecision 等
```

**职责边界**：

| 模块 | 负责 | 不负责 |
|---|---|---|
| Voice Gateway | WebSocket 连接、音频收发、打断控制、thinking 状态推送 | 面试逻辑、状态管理 |
| ASR/TTS Service | 语音↔文本转换 | 语义理解、内容生成 |
| Interviewer Agent | 根据决策生成问题文本 | 评价、策略决策 |
| Evaluator Agent | 评价回答 + 决定下一步动作 | 生成问题文本、语音处理 |
| Interview Graph | 流程编排、条件路由 | 具体 Agent 逻辑 |
| Interview Session | 状态持久化、与主会话关联 | 业务决策 |

**与现有 InterviewQAAgent 的关系**：共存，不替代。InterviewQAAgent 继续离线生成面试题供用户参考；模拟面试是独立的新功能。用户参考过的题目列表会传入 Interview Graph，避免重复出题。

---

## InterviewState

```python
class InterviewState(TypedDict, total=False):
    # 会话标识
    session_id: str                    # 关联主会话 ID
    interview_id: str                  # 本次面试唯一 ID

    # 面试配置（初始化时注入，只读）
    jd_analysis: dict                  # 从主会话注入
    profile: dict                      # 从主会话注入
    target_position: str
    referenced_questions: list[str]    # 用户已参考的面试题（避免重复出题）

    # 动态配置（Evaluator 修改）
    difficulty_level: str              # easy/medium/hard
    interview_mode: str                # technical/behavioral/mixed

    # 面试进程
    phase: str                         # opening → core_probing → closing
    current_question: str              # Interviewer 写入
    current_answer: str                # Voice Layer 写入（ASR 结果）
    turn_count: int                    # Graph 每轮 +1
    max_turns: int                     # 默认 10

    # 历史
    conversation_history: list[dict]   # [{role, content, timestamp}]

    # 评价（Evaluator 写入）
    dimension_scores: dict[str, float] # 动态维度，加权平均更新
    current_evaluation: dict           # 当前轮评价
    strengths: list[str]               # 累积
    weaknesses: list[str]              # 累积

    # 策略（Evaluator 写入，Graph 读取做路由）
    next_action: str                   # 追问/切换话题/提高难度/降低难度/结束面试
    covered_topics: list[str]
    pending_topics: list[str]

    # 状态标记
    is_active: bool
    is_complete: bool
    completion_reason: str             # max_turns/all_topics_covered/user_ended

    # 最终报告
    final_report: dict

    # 可观测
    workflow_trace: Annotated[list, operator.add]
```

**持久化方案**：InterviewSessionService 复用现有 SessionStore 接口（Redis key-value），面试会话通过 `session_id` 与主会话关联。嵌套结构（dict/list）序列化为 JSON 字符串存储。面试结束后 final_report 同时写入 MySQL interview_logs 表。

**维度评分更新**：首轮直接用 current_score；后续轮 `old * 0.7 + new * 0.3`。维度名称由 Evaluator 根据 JD 动态生成。turn_count 在 evaluate 节点内递增，评分更新在同一节点内完成，不存在时序问题。

---

## LangGraph 流程

```
start → open_interview → ask_question → wait_answer → evaluate → decide_next
                          ↑                                  │
                          │         ┌────────────────────────┤
                          │         ▼         ▼          ▼        ▼
                          │    follow_up  next_topic  adjust   finish
                          │         │         │          │        │
                          └─────────┴─────────┴──────────┘        │
                                                    generate_report → END
```

| 节点 | 一行说明 |
|---|---|
| open_interview | 生成开场白，初始化维度和待考察话题，标记 referenced_questions 中已准备的题为低优先级 |
| ask_question | Interviewer 根据 Evaluator 决策生成问题，优先跳过 referenced_questions 中的题 |
| wait_answer | 空操作，等待 Voice Gateway 注入 current_answer 后恢复 |
| evaluate | Evaluator 评价回答，输出评分+决策，递增 turn_count |
| decide_next | 条件路由，读 next_action 字段 |
| follow_up / next_topic | pass-through，回到 ask_question |
| adjust | 更新 difficulty_level，回到 ask_question |
| finish | 标记 is_complete |
| generate_report | 汇总评价生成报告 |

**条件路由规则**：

| 条件 | 动作 |
|---|---|
| 回答正确但浅显，有深入空间 | 追问 |
| 回答优秀，当前话题已充分考察 | 切换话题 |
| 回答吃力，频繁出错 | 降低难度 |
| 回答轻松，快速准确 | 提高难度 |
| 所有核心话题已覆盖 或 达到 max_turns | 结束面试 |

---

## WebSocket 协议

**客户端 → 服务端**：

| 类型 | 格式 |
|---|---|
| 音频帧 | 二进制 PCM16 16kHz mono |
| interrupt | `{"type": "interrupt"}` |
| end_of_speech | `{"type": "end_of_speech"}` |
| text | `{"type": "text", "content": "..."}` |

**服务端 → 客户端**：

| 类型 | 格式 | 说明 |
|---|---|---|
| asr_final | `{"type": "asr_final", "text": "..."}` | ASR 结果 |
| thinking | `{"type": "thinking"}` | ASR 完成后立刻发送，前端显示"面试官正在思考..." |
| llm_token | `{"type": "llm_token", "content": "..."}` | LLM 流式 token |
| tts_start / tts_end | JSON | TTS 边界 |
| TTS 音频 | 二进制 PCM16 24kHz mono | |
| interrupted | `{"type": "interrupted"}` | 打断确认 |
| error | `{"type": "error", "message": "..."}` | |
| done | `{"type": "done", "report": {...}}` | 面试结束，附报告 |

**音频格式**：输入 PCM16 16kHz，输出 PCM16 24kHz。前端需分别处理录音和播放的采样率。

---

## 打断机制

### 打断链路

_voice gateway 的 `_processor` 是单线程串行执行 ASR → Interview Graph → TTS。Graph 执行期间（6-10s）队列不消费，interrupt 消息堆积。_

**解决**：InterviewHandler.process_answer 改为分步执行：

```
步骤1: evaluate（Evaluator LLM 调用，~3s）
  → 每步 LLM 调用前检查 interrupt_event
  → 被打断：保存中间状态，返回 None
步骤2: decide_next（纯函数，<1ms，无需检查）
步骤3: ask_question（Interviewer LLM 调用，~3s）
  → 调用前检查 interrupt_event
  → 被打断：保存中间状态，返回 None
```

### 打断阶段与恢复规则

| 打断发生在 | 中间状态 | 恢复策略 |
|---|---|---|
| evaluate 进行中 | evaluation 未完成 | 下一轮重新 evaluate（current_answer 保留） |
| evaluate 完成，ask_question 未开始 | evaluation 已保存 | 下一轮跳过 evaluate，直接 ask_question |
| ask_question 进行中 | question 未生成 | 下一轮用 evaluation 决策重新 ask_question |
| TTS 播放中 | question 已生成 | question 保留，下一轮直接用 |

**恢复规则**：打断后 state 中保存 `interrupt_checkpoint` 字段，记录已完成的步骤。下次 process_answer 从断点继续，不重复已完成的步骤。

---

## 分阶段实施计划

### Phase 1: Interview Graph 核心（REST API 验证）

**目标**：通过 REST API 验证 Interview Agent 的决策逻辑，不涉及语音。

**新增**：
- `interview/state.py`, `graph.py`, `nodes.py`, `edges.py`, `session_service.py`, `report.py`
- `agents/interviewer.py`, `agents/evaluator.py`
- `api/interview.py`
- `tests/test_interview_graph.py`, `tests/test_evaluator.py`

**修改**：
- `models/schemas.py` — 新增 InterviewTurn, EvaluationDecision, InterviewReport
- `agents/__init__.py` — 注册新 Agent
- `main.py` — 注册路由

**验收**：
- [ ] POST /api/interview/start 创建面试，返回开场白
- [ ] POST /api/interview/{id}/answer 提交文字回答，返回下一个问题或报告
- [ ] Evaluator 输出结构化决策，条件路由正确执行
- [ ] 面试结束后生成完整评价报告
- [ ] 状态持久化到 SessionStore
- [ ] referenced_questions 传入后，面试官避免重复出题
- [ ] 所有测试通过

### Phase 2: Voice Layer（独立可测）

**目标**：实现语音输入输出，独立于面试逻辑可测试。

**新增**：
- `voice/gateway.py`, `asr_service.py`, `tts_service.py`, `audio_utils.py`, `protocol.py`
- `tests/test_asr_service.py`, `tests/test_tts_service.py`
- `frontend/src/composables/useVoiceChat.ts`
- `frontend/src/components/VoiceInterviewPanel.vue`

**修改**：
- `main.py` — 注册 WebSocket
- `config.py` — ASR/TTS 配置

**验收**：
- [ ] 浏览器录音 → ASR 转写 → 文字展示（回环测试）
- [ ] 文字输入 → TTS → 浏览器播放（回环测试）
- [ ] Silero VAD 正确检测语音活动
- [ ] thinking 状态正确推送和展示

### Phase 3: 集成 + 打断

**目标**：Voice + Interview 连通，支持打断。

**新增**：
- `voice/interview_handler.py`

**修改**：
- `voice/gateway.py` — 集成 InterviewHandler，分步执行 + interrupt 检查
- `frontend/src/components/VoiceInterviewPanel.vue` — 完整面试 UI

**验收**：
- [ ] 语音问 → ASR → Interview Agent → TTS → 听到回复，完整链路
- [ ] 面试官开场白正常播出
- [ ] 用户打断 AI 后能继续下一轮
- [ ] 打断发生在不同阶段时状态正确恢复
- [ ] 面试结束后展示评价报告

### Phase 4: 主系统集成

**修改**：
- `api/sessions.py` — 面试意图接入
- `graph/workflow.py` + `graph/intent.py` — 新增 interview_sim 意图

**验收**：
- [ ] 主系统意图分类支持"开始模拟面试"
- [ ] 面试结果写入跨会话记忆
- [ ] WebSocket 断开后可恢复面试
