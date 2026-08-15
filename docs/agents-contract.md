# Agents & Tools Contract（v3）

> 所有 Agent 与工具的输入/输出/权限契约。运行时暂为文档级约束，实施时按需校验。
> 参考：ai-career-copilot 的 agents_contract.md。

## 1. 工具契约

| 工具 | 输入 | 输出 | 绑定能力单元 | 失败降级 |
|------|------|------|-------------|---------|
| similar_cases (RAG) | query, category, n_results | cases[] | gap_analyzer | 返回空，LLM 继续分析 |
| question_bank | category, topic, difficulty, count | questions[] | interview_qa | 返回空，LLM 自生成 |
| best_practices | topic, industry | practices | content_generator, cover_letter | 返回空，LLM 直接生成 |
| keyword_optimizer | resume_keywords, jd_keywords | 覆盖率+建议 | content_generator | 返回空 |
| template_search | style | templates[] | content_generator, cover_letter | 返回默认模板 |
| file_parser | file_path | text | API 层（上传解析） | 明确错误信息 |
| html_renderer | template_name, data | html | 导出端点 | 明确错误信息 |

**工具调用约束**：
- 工具调用发生在 `BaseAgent.run()` 的工具循环内（上限 5 轮）
- 工具结果以 TOOL 角色消息回填，由 LLM 自行消化
- 工具执行异常不抛给调用方，以错误 JSON 返回给 LLM

## 2. Agent 能力单元契约

| 能力单元 | 读取 | 写入 | 禁写 | 触发 |
|---------|------|------|------|------|
| planner | user_message, 状态摘要 | intent, intent_reason, route, execution_plan, workflow_trace | 全部业务字段 | 每轮入口 |
| jd_analyzer | jd_text | jd_analysis, jd_analyzed_version | 其余 | upload_jd / 版本过期 |
| profile_extractor | resume_text, existing_profile | profile, profile_analyzed_version | 其余 | upload_profile / 版本过期 |
| gap_analyzer | jd_analysis, profile | gap_analysis, gap_based_jd/profile | 其余 | gap_analysis 意图 / 级联 |
| content_generator | profile, jd, gap, user_instructions | resume_content, content_iterations, content_based_jd/profile | render_config | content_edit 意图 / 级联 |
| reviewer | resume_content, jd, profile | review_result | 其余 | parallel_post（规则预检短路） |
| html_renderer | resume_content | render_config | 其余 | render_edit 意图 / 级联 |
| interview_qa | jd, profile, gap | interview_questions, interview_based_jd/profile | 其余 | parallel_post / 兜底 |
| interview_reviewer | interview_questions, jd, profile | interview_review_result | 其余 | 面试题生成后 |
| question | 全状态（只读） | answer, workflow_trace | 所有业务字段 | ask_question 意图 |
| cover_letter | profile, jd, gap, channel | cover_letter, workflow_trace | 其余 | generate_cover_letter 意图 |
| clarifier | user_message, 会话状态 | clarification_* | 其余 | 数据不足 / 渠道选择 |

## 3. 边界约束

1. 能力单元只能写入契约允许的字段，越权视为 Bug
2. 所有单元通过 GraphState 读写，不直接访问数据库（Memory 由 services 层负责）
3. 单元间不直接互调，由 planner/路由调度
4. 增量编辑：写入下游产物时必须同步写入其"基于版本"（gap/content/interview）
5. 自由问答（question）与导出不修改任何业务状态

## 4. 记忆契约（services 层）

| 操作 | 位置 | 说明 |
|------|------|------|
| 档案合并 | services/memory_service.py upsert_profile | 规则合并（技能去重/经历按 key 去重），零 LLM |
| 档案读取 | get_profile / build_summary | 会话开始注入 memory_summary |
| 偏好读取 | get_preferences | user_preferences 表 |
| 提炼（consolidate） | 后续里程碑 | LLM 一步，输出经白名单校验后落库 |
