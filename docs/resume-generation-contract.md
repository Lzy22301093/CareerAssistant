# 简历生成区 + 简历库导入 · 前后端契约（前端对接用）

> **日期**: 2026-09-08（向导 8 模块重构）
> **用途**: 简历生成区（8 步向导）与简历库导入的前后端契约。
> **后端基线**: 557 passed（含 wizard / template / import / export）。

---

## 0. 一句话

- **生成区**＝ 8 步向导，步骤数据逐步存 `resume_drafts`（暂存退出），最后一步调 `/api/resume-generation/generate` 生成简历并可**直入简历库**（`source=generation`）。
- **简历库导入**：① 生成区产物由 `import_to_library=true` 直接入库；② 上传文件走 `POST /api/resumes/import-upload`；③ 已有 "从会话导入" 保留。
- 生成区产物与简历工作台的**框选/区域改写天然联动**（同一 `ResumeContent {sections}` 模型）。

---

## 1. 8 步向导数据流（v2 模块拆分）

```
01 基本信息 + 投递方向 ──► basic_info + directions（1-3）
02 教育经历 ──► educations: WizardEducationEntry[]（学校/层次/专业/起止含「至今」/GPA/排名/课程可选）
03 专业技能 ──► skills: WizardSkillItem[]（name+level）+ basic_info.certifications
04 实习经历 ──► internships: WizardExperienceEntry[]（公司/岗位/起止/工作内容/成果 + 可选 STAR）
05 项目经历 ──► projects: WizardExperienceEntry[]（项目名/角色/起止/技术栈/工作/成果 + 可选 STAR）
06 自我评价 ──► soft_info（personality/vision/disinterested/self_eval；disinterested 不进简历）
07 证件照 ──► photo_id
08 生成与导出 ──► 预览微调（module_order）+ generate + export
   └─ 每步可「暂存」：POST /api/resume-generation/draft（step + 快照，含 draft_version: 2）
```

**草稿兼容**：前端 `restore` 自动迁移旧版——`basic.education` 文本 → `educations`；混合 `experiences` 按 `exp_type` 分流到 `internships`/`projects`；`skills` 字符串 → `{name,level}`。

**暂存（resume_drafts，每用户一份）**：
- 保存：`POST /api/resume-generation/draft` body `{step: 1-8, data: {...}}`
- 读取：`GET /api/resume-generation/draft` → `{step: number|null, data: {}, updated_at}`
- 清空：`DELETE /api/resume-generation/draft`

---

## 2. 关键接口（全部需 `Bearer token`）

### 2.1 生成区
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/resume-generation/draft` | 保存草稿 |
| GET | `/api/resume-generation/draft` | 读草稿 |
| DELETE | `/api/resume-generation/draft` | 清草稿 |
| POST | `/api/resume-generation/star` | `{experiences:[WizardExperienceCreate]}` → `{items:[StarResultItem]}`（实习/项目步共用，LLM） |
| POST | `/api/resume-generation/experiences/structure` | `{text, directions?}` → `{items:[ExperienceDraftItem]}`（实习/项目步 AI 包装） |
| POST | `/api/resume-generation/experiences/generate` | `{directions?, count?}` → `{items:[ExperienceDraftItem]}` |
| POST | `/api/resume-generation/photo` | multipart `file`（jpg/jpeg/png/webp，≤5MB） |
| GET | `/api/resume-generation/photo` | 当前照片元信息（无则 `null`） |
| GET | `/api/resume-generation/photo/file?id=` | 照片二进制（须带鉴权，前端用 blob+objectURL） |
| POST | `/api/resume-generation/generate` | 见 2.2 |
| POST | `/api/resume-generation/export` | `{title, content, format, photo_id?}` → 下载 |

### 2.2 `POST /api/resume-generation/generate`（v2）
```json
{
  "title": "张三·后端开发工程师简历",
  "basic_info": { "name":"张三","email":"...","phone":"...","location":"...","birthday":"...","gender":"...",
                  "certifications":["CET-6"] },
  "directions": ["后端开发工程师"],
  "educations": [ { "school":"北京大学","degree":"本科","major":"软件工程",
                    "start":"2022-09","end":"2026-06","current":false,
                    "gpa":"3.8/4.0","rank":"5/60","courses":"数据结构" } ],
  "skills": [ { "name":"Python","level":"掌握" } ],
  "internships": [ { "company":"A公司","title":"后端实习生","start":"2024-06","end":"2024-09","current":false,
                     "duration":"","tech_stack":"","duty":"...","achievement":"...",
                     "situation":"","task":"","action":"","result":"" } ],
  "projects": [ { "company":"校园二手平台","title":"后端负责人","start":"2023-09","end":"","current":true,
                  "tech_stack":"FastAPI","duty":"...","achievement":"...",
                  "situation":"","task":"","action":"","result":"" } ],
  "soft_info": { "personality":"...","vision":"...","disinterested":"...","self_eval":"..." },
  "photo_id": 1,
  "module_order": ["基本信息","求职意向","教育背景","实习/工作经历","项目经历","技能","个人优势","证书/荣誉"],
  "page_preference": "one_page",
  "polish": true,
  "import_to_library": true,
  "template": "campus_one_page"
}
```
- **兼容**：`experiences: StarResultItem[]` 仍可单独提交；仅当 `internships` 与 `projects` 均为空时按 `exp_type` 分流。
- `duration` 可空：组装时用 `format_period(start,end,current)`，`current=true` 显示「至今」。
- 教育展示：`学校 · 层次 · 专业 · 起–止（GPA …；排名 …）`，课程可另起「主修课程：…」。
- 技能展示：`Python（掌握）`。

响应与模块集同旧版：`content.sections` + 可选 `document`；一页纸仍会按模板 `max_experiences` 收紧。

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
