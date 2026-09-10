# 简历生成区 + 简历库导入 · 前后端契约（前端对接用）

> **日期**: 2026-09-06
> **用途**: 另一对话正在重做前端；本文档给出**简历生成区（8 步向导）与简历库导入**的后端契约，
> 前端按此实现 UI，**不要改动后端**（后端已实现并测试全绿，512+ 用例）。
> **后端基线**: 514 passed（含新增 test_resume_wizard_service / test_resume_import_service）。

---

## 0. 一句话

- **生成区**（新页面，建议入口：功能墙卡片"简历生成"）＝ 8 步向导，步骤数据逐步存 `resume_drafts`（暂存退出），最后一步调 `/api/resume-generation/generate` 生成简历并可**直入简历库**（`source=generation`）。
- **简历库导入**：① 生成区产物由 `import_to_library=true` 直接入库；② 上传文件走 `POST /api/resumes/import-upload`（PDF/DOCX/TXT/MD → 解析 → 入库，`source=upload`）；③ 已有 "从会话导入" 保留。
- 生成区产物与简历工作台的**框选/区域改写天然联动**（同一 `ResumeContent {sections}` 模型，入库自动拆 `ResumeSection`，`section_type` 按标题推断，新增 `objective` 类型）。

---

## 1. 8 步向导数据流

```
01 基础信息 ──► (表单) basic_info
02 画像与方向 ──► GET /api/profile/directions/recommend + confirm  → directions: string[]（1-3）
03 经历补充 ──► experiences: WizardExperienceCreate[]
04 STAR 结构化 ──► POST /api/resume-generation/star  → StarResultItem[]（可逐条编辑）
05 软性信息 ──► soft_info（可直接复用 /api/profile/soft-info/generate + save，或本地表单）
06 证件照 ──► POST /api/resume-generation/photo（multipart）→ photo_id
07 预览微调 ──► module_order: string[]（模块标题顺序，可上下移）+ 逐模块文本可编辑
08 生成与导出 ──► POST /api/resume-generation/generate（含 page_preference 1/2 页）→ content + document
   └─ 每步可「暂存退出」：POST /api/resume-generation/draft（step + 本步数据快照）
```

**暂存退出（resume_drafts，每用户一份）**：
- 保存：`POST /api/resume-generation/draft` body `{step: 1-8, data: {...}}`（data 为任意 JSON，前端自存该步表单数据）。
- 读取：`GET /api/resume-generation/draft` → `{step: number|null, data: {}, updated_at}`。
- 清空：`DELETE /api/resume-generation/draft`。

---

## 2. 关键接口（全部需 `Bearer token`）

### 2.1 生成区
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/resume-generation/draft` | 保存草稿（暂存退出） |
| GET | `/api/resume-generation/draft` | 读草稿 |
| DELETE | `/api/resume-generation/draft` | 清草稿 |
| POST | `/api/resume-generation/star` | `{experiences:[WizardExperienceCreate]}` → `{items:[StarResultItem]}`（LLM，~30-50s，前端超时建议 ≥180s） |
| POST | `/api/resume-generation/photo` | multipart `file`（jpg/jpeg/png/webp，≤5MB）→ `{id,filename,url,created_at}`（每用户一张，覆盖） |
| GET | `/api/resume-generation/photo` | 当前照片元信息（无则 `null`） |
| GET | `/api/resume-generation/photo/file?id=` | 照片二进制（`<img :src>` 可直接用） |
| POST | `/api/resume-generation/generate` | 见 2.2（LLM 润色可关；~30-90s，前端超时建议 ≥300s） |
| POST | `/api/resume-generation/export` | `{title, content, format}` → 下载文件（`format`: docx \| html \| md \| json；docx 用 python-docx，html 可浏览器打印转 PDF） |

共用：`generate`/`star` 失败映射——无 key 503、业务 422、LLM 失败 502。

### 2.2 `POST /api/resume-generation/generate` 请求/响应
请求（`WizardGenerateRequest`）：
```json
{
  "title": "我的新简历",
  "basic_info": { "name":"张三","email":"...","phone":"...","location":"...","birthday":"...","gender":"...",
                  "education":["北京大学 本科 软件工程 2022-2026"], "certifications":["CET-6"], "skills":["Python"] },
  "directions": ["后端开发工程师", "算法工程师"],
  "experiences": [ { "exp_type":"项目|实习|竞赛|课程|校园", "company":"省数学竞赛", "title":"参赛选手",
                     "situation":"...","task":"...","action":"...","result":"..." } ],
  "soft_info": { "personality":"...","vision":"...","disinterested":"...","self_eval":"..." },
  "photo_id": 1,
  "module_order": ["基本信息","求职意向","教育背景","实习/工作经历","项目经历","技能","自我评价","证书/荣誉"],
  "page_preference": "one_page | two_pages",
  "polish": true,
  "import_to_library": true
}
```
响应：
```json
{
  "content": { "sections":[{"title":"基本信息","content":"姓名：张三"}], "raw_text":"..." },
  "document": { 简历库文档（ResumeDocumentDetailOut，含 versions/current_version）| null }
}
```
- `content.sections` 的顺序 = `module_order` 的生效结果（未知标题排后）。
- `import_to_library=true` 时：建文档（`source=generation`）+ v1（自动拆 `ResumeSection`），`document` 返回其详情；`false` 时仅返回 `content`（前端预览用）。
- **默认模块集**（后端常量，07 步可只展示/重排这些）：`基本信息 / 求职意向 / 教育背景 / 实习/工作经历 / 项目经历 / 技能 / 自我评价 / 证书/荣誉`。

### 2.3 简历库导入
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/resumes/import-upload` | multipart `title`(Form) + `file`(PDF/DOCX/TXT/MD，≤20MB) → 文档详情（201） |
| POST | `/api/resumes/import-generated` | `{title, content:{sections,raw_text}, page_preference}` → 文档详情（201） |

- `import-upload`：文件 → 文本 → **启发式拆区域**（标题行=含教育/经历/项目/技能/证书/自我评价等关键词的短行；无命中则单块"正文"）→ 入库（`source=upload`，自动拆 `ResumeSection`）。
- 启发式是保底能力；**AI 结构化解析**（逐字段画像）仍走聊天上传路径，本文档不覆盖。

### 2.4 复用已有接口
- 方向推荐：`POST /api/profile/directions/recommend`（180s 超时）、`confirm`（保存 1-3 到画像 `target`）。
- 软性信息：`POST /api/profile/soft-info/generate`（AI 生成）、`save`（写成 `soft` 画像条目）。
- 简历库：`GET /api/resumes`、`POST /api/resumes/{id}/versions`、区域改写 `/sections/{id}/rewrite`、版本页数偏好 `versions/{id}/page-preference`（已有）。

---

## 3. 与简历工作台（框选/区域改写）的联动 —— 关键约定

1. **同一 `ResumeContent` 模型**：生成区产物 = 库内文档版本内容；`add_version` 自动按 `content.sections` 拆 `ResumeSection`（`page_number` 顺排、`sort_order` 按数组序、`section_type` 按标题推断）。
2. **区域类型**在原有基础上**新增 `objective`（求职意向）**：`求职意向/意向/目标岗位/目标方向` → `objective`；其余不变（header/summary/education/experience/project/skill/certification/custom）。
3. **框选坐标基准**：简历库预览为**板块卡片列表**（bbox 是卡片坐标）。建议前端预览统一用"模块卡片"形态（与 07 步结构预览一致），**不要**引入"渲染后 HTML 像素框"另一套坐标，否则 bbox 错位。
4. **区域改写寻址**按 `ResumeSection.id`，与生成区产物无感——生成后进库即可框选/对话/改写（改写采纳 → 新版本，可回滚）。
5. **证件照**：`resume_photos`（每用户一张）；前端 `<img src="/api/resume-generation/photo/file?id=x">` 引用；渲染/导出带图是后续增强（当前 content 不含照片字段）。
6. **页数偏好**：存 `render_config.page_preference`（版本级），08 步单选后入库即生效。

---

## 4. 边界与注意事项（前端要知道的）
- `generate` 的 `polish=true` 失败会**自动回退**为未润色内容（不报错），前端按正常成功处理。
- `star` 需要一个 LLM 调用；空经历列表直接返回 `[]`（不发请求也行）。
- 上传解析是**启发式**，拆分质量有限；用户可在工作台用"区域对话/框选"修正。
- **Word/PDF 下载未实现**（后端无 docx/pdf 导出）；生成完成页可先提供"预览(html)" + "下载 html/json/markdown"（`/api/sessions/{id}/export` 是会话路径；库内版本可前端拼 text）。docx/pdf 导出作为后续增强。
- 所有 LLM 端点超时放宽：star 180s、generate 300s（对齐后端 AGENT_TIMEOUT=120s 每 agent）。
