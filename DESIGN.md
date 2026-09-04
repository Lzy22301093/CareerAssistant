# CareerAssistant — Frontend Design Direction

> 本文件定义 CareerAssistant 的视觉设计语言。所有前端实现应以此为准。
> 版本：draft-1 · 2026-08-18

---

## 一、设计分析：为什么需要一套独立的视觉语言

### 1. 这个产品解决什么问题？

求职是一个**高压力、高不确定性**的过程。用户面对一个目标岗位时，核心焦虑是：

- "我的简历和这个 JD 匹配吗？差距在哪？"
- "我的简历够好吗？怎么改？"
- "面试会问什么？我怎么准备？"

CareerAssistant 把这三个问题压缩成一个流程：**贴入 JD + 简历 → 得到差距分析 + 优化简历 + 面试题库 + 求职信**。核心价值是**消除不确定性**——把模糊的焦虑变成结构化的、可执行的行动方案。

### 2. 目标用户是谁？

- **正在投递简历的求职者**（应届生 + 3-5 年经验者为主）
- 中国互联网/科技行业求职者（MIMO 模型、PingFang SC 字体、中文界面）
- 使用场景：坐在电脑前，打开一个目标 JD，准备投递前的最后冲刺
- 心理状态：**紧张、希望被认真对待、需要确定感**

### 3. 产品应该给用户什么样的心理感受？

**"这是一个认真对待我职业前途的工具。"**

具体来说：
- **信任感**：输出的简历、分析、面试题是专业的、可靠的，不是玩具
- **掌控感**：我能清楚看到系统在做什么、进展到哪、结果是什么
- **专注感**：界面不分散注意力，让我专注于内容本身
- **安全感**：我的数据被认真处理，错误时我能理解发生了什么

不应有的感受：
- "这是一个 AI 玩具" → 过度使用渐变、发光效果、AI 图标
- "这是一个通用后台" → Dashboard 模板感、千篇一律的卡片布局
- "信息太多了" → 视觉噪音干扰我对核心内容的阅读

### 4. 最适合的视觉设计方向是什么？

**编辑型文档工具风格（Editorial Document Tool）**

参考气质：Notion 的克制、Linear 的精确、VS Code 的功能至上、Stripe Docs 的信息密度。

这个方向的核心是：**界面退后，内容上前**。UI 的存在感降到最低，让用户感觉在阅读一份精心排版的文档，而不是在操作一个软件界面。

### 5. 为什么这个方向适合，其他方向不适合？

| 方向 | 为什么不合适 |
|------|-------------|
| **SaaS Dashboard**（如 Stripe Dashboard） | CareerAssistant 不是仪表盘——用户不需要实时监控指标，而是阅读分析结果。Dashboard 的卡片网格布局会把结构化的分析结果打碎成互不相关的碎片 |
| **AI Chatbot**（如 ChatGPT 克隆） | 虽然有对话界面，但核心价值不在对话本身，而在结构化的分析产出。纯聊天界面会隐藏这些产出，降低信息密度 |
| **Creative Portfolio**（如 Dribbble 展示型） | 过度的视觉表现会喧宾夺主。用户要的是简历内容好不好，不是界面好不好看 |
| **文档协作工具**（如 Google Docs） | 接近但不完全对——CareerAssistant 是单用户、结果导向的，不需要多人协作的 UI 模式 |
| **编辑型文档工具** ✓ | 最契合——用户输入原始材料（JD + 简历），系统输出结构化的专业文档（分析报告 + 优化简历 + 面试准备）。界面需要做的就是清晰地呈现这些文档 |

---

## 二、Visual Design Direction

### Design Concept

**"Preparation Room"** — 准备室

用户进入的不是一个花哨的 AI 界面，而是一个**安静、有序、专业的准备空间**。左边是对话——用户和一个资深职业顾问的交流；右边是产出——顾问整理好的分析报告和建议。

视觉隐喻：一份摆在干净桌面上的专业文件夹，里面整齐地装着 JD 分析、差距报告、优化简历和面试笔记。

### Visual Personality

- **安静**（Quiet）：低饱和度、高对比度的文字、留白充足
- **精确**（Precise）：清晰的信息层级、一致的间距、规整的对齐
- **温暖**（Warm）：不是冷冰冰的企业灰，而是带微暖调的中性色
- **专注**（Focused）：没有装饰性元素争夺注意力

不是：活泼的、游戏化的、科技感的、未来感的

### Typography

**放弃 Inter / Roboto / 系统默认字体栈。**

| 角色 | 字体 | 说明 |
|------|------|------|
| 中文正文 | **Noto Sans SC**（思源黑体） | Google 与 Adobe 联合开发，字形规范，屏幕渲染优秀，免费商用。比微软雅黑更现代、更中性 |
| 英文正文 / 数字 | **IBM Plex Sans** | IBM 设计，几何感强但不冰冷，与思源黑体视觉协调。比 Inter 有辨识度 |
| 代码 / 数据 | **IBM Plex Mono** | 与 IBM Plex Sans 同族，session ID、技术栈标签等场景使用 |
| 简历标题 | **Noto Serif SC**（思源宋体） | 仅在简历预览中使用，增加文档正式感 |

字号体系（基于 16px 基准）：

```
11px  — 时间戳、极次要元数据
12px  — 标签文字、表格辅助信息
13px  — 正文（对话消息、表格内容）
14px  — 副标题、描述文字
16px  — 正文基准（简历内容）
20px  — 板块标题（JD 分析、差距报告等）
24px  — 页面级标题
```

行高：
- 正文：1.6（中文阅读舒适度）
- 标题：1.3
- 表格：1.5

字重使用：
- 400（Regular）：正文
- 500（Medium）：标签、小标题、强调
- 600（Semibold）：板块标题
- 不使用 700+——避免"大声喊叫"的感觉

### Color System

**远离 Element Plus 默认蓝。远离紫色渐变。**

#### 中性色（Neutrals）— 界面骨架

```
Gray-950: #0f1117  — 仅用于深色模式（预留）
Gray-900: #1a1d24  — 主要文字
Gray-700: #3d4250  — 次要文字
Gray-500: #6b7280  — 辅助文字、占位符
Gray-400: #9ca3af  — 禁用状态文字
Gray-300: #d1d5db  — 边框
Gray-200: #e5e7eb  — 分割线
Gray-100: #f3f4f6  — 表头背景、hover 背景
Gray-50:  #f9fafb  — 页面背景
White:    #ffffff  — 卡片、输入框背景
```

特点：偏暖灰（slate 色系），不是纯灰。给界面一种"纸张"的质感而非"屏幕"的冰冷。

#### 主题色（Accent）— 操作引导

```
Accent-600: #2563eb  — 主按钮、链接、活跃状态
Accent-500: #3b82f6  — hover 状态
Accent-100: #dbeafe  — 轻量背景（系统消息、选中状态）
Accent-50:  #eff6ff  — 极轻背景
```

选择蓝色而非紫色的原因：
- 蓝色在职业场景中传达**信任、专业、稳定**
- 紫色在 AI 产品中已被过度使用（"AI = 紫色渐变"已成为刻板印象）
- 蓝色与绿色/红色的语义色不冲突，色盲友好

#### 语义色（Semantic）— 状态传达

```
Success-600: #16a34a  — 匹配度高、通过、strength
Success-50: #f0fdf4  — success 背景

Warning-600: #ca8a04  — 匹配度中、major gap
Warning-50: #fefce8  — warning 背景

Danger-600: #dc2626  — critical gap、高重要性、hard 难度
Danger-50: #fef2f2  — danger 背景

Info-600: #0284c7  — 系统消息、category 标签
Info-50: #f0f9ff  — info 背景
```

对比度：所有文字色在对应背景上的 WCAG AA 对比度 ≥ 4.5:1。

### Spacing

**基于 4px 基准的间距系统**（不使用 8px 基准——4px 提供更精细的控制）：

```
--space-1:  4px   — 图标与文字间距、紧凑元素内部
--space-2:  8px   — 相关元素间距（标签之间、按钮组内）
--space-3:  12px  — 表单 label 与 input 间距
--space-4:  16px  — 板块内元素间距、卡片内 padding
--space-5:  20px  — 板块之间间距
--space-6:  24px  — 大板块间距
--space-8:  32px  — 页面区域间距
--space-10: 40px  — 页面级留白
--space-12: 48px  — 登录页等大留白场景
```

原则：
- **相关内容靠近，无关内容拉开**（格式塔 proximity 原则）
- 左右面板之间的间距用 border + 0 padding，不用 margin——减少视觉断裂
- 板块内部 padding 统一 `16px`，板块之间 margin 统一 `20px`

### Border / Radius

**克制使用圆角。这不是一个"可爱的"产品。**

```
--radius-sm:  2px  — 按钮、输入框、标签
--radius-md:  4px  — 卡片、表格、面板
--radius-lg:  6px  — 对话气泡、弹窗
--radius-full: 9999px — 圆形头像、状态指示器
```

对比现状（Element Plus 默认 4px + 项目中 8px 气泡）：
- 消息气泡从 8px 降到 6px——更克制，不追求"气泡"感
- 卡片保持 4px——方正感传达专业
- 按钮 2px——几乎方正，增加正式感

边框使用：
```
--border-light:  1px solid #e5e7eb  — 分割线、面板分隔
--border-medium: 1px solid #d1d5db  — 输入框默认态
--border-focus:  1px solid #2563eb  — 输入框聚焦态（+ box-shadow: 0 0 0 3px rgba(37,99,235,0.1)）
```

### Shadow

**几乎不用阴影。**

```
--shadow-sm:  0 1px 2px rgba(0,0,0,0.04)   — 下拉菜单、tooltip
--shadow-md:  0 2px 8px rgba(0,0,0,0.06)   — 悬浮卡片、drawer
--shadow-lg:  0 4px 16px rgba(0,0,0,0.08)  — 模态框
```

原则：
- 不给普通卡片加阴影——用 border 分隔，不是 shadow
- 阴影偏暖（rgba 黑而非纯黑）
- 只在"浮起"的元素上使用（dropdown、drawer、modal）
- 不使用多层阴影、发光阴影、彩色阴影

### Layout / Grid

#### 主页：双栏分割布局

```
┌─────────────────────────────────────────────────────────┐
│ Header (48px)                                           │
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  Chat Panel  │         Result Panel                     │
│  (380px)     │         (flex: 1)                        │
│              │                                          │
│              │  ┌──────────────────────────────────┐    │
│              │  │ Tab Bar                          │    │
│              │  ├──────────────────────────────────┤    │
│              │  │                                  │    │
│              │  │  Tab Content (scrollable)        │    │
│              │  │                                  │    │
│              │  └──────────────────────────────────┘    │
│              │                                          │
├──────────────┴──────────────────────────────────────────┤
│ Input Area (ChatPanel 底部，ResultPanel 无底部栏)        │
└─────────────────────────────────────────────────────────┘
```

- Chat Panel 宽度：380px（比当前 400px 稍窄，给右侧更多空间）
- 最小视口宽度：1024px（不考虑移动端——这是一个桌面工具）
- Header 高度：48px（比当前 60px 更紧凑）
- Result Panel 内部 tab 内容区：可滚动，底部留 24px padding

#### 登录/注册页：左图右表分割

```
┌────────────────────────────────────┐
│                                    │
│   ┌──────────┐  ┌──────────────┐  │
│   │          │  │              │  │
│   │  品牌区   │  │   表单区     │  │
│   │  (40%)   │  │   (60%)     │  │
│   │          │  │              │  │
│   └──────────┘  └──────────────┘  │
│                                    │
└────────────────────────────────────┘
```

- 左侧：白色/浅灰背景，产品名 + 一句价值描述 + 抽象的文档线条装饰（纯 CSS，不用图片）
- 右侧：白色背景，居中的表单
- **放弃紫色渐变背景**——这是"AI 产品"的刻板印象，与求职的严肃性不匹配

### Component Style

#### 按钮

```
Primary:    bg=#2563eb, text=white, radius=2px, padding=8px 16px, font-weight=500
Secondary:  bg=white, text=#3d4250, border=1px solid #d1d5db, radius=2px
Ghost:      bg=transparent, text=#6b7280, hover → text=#1a1d24
Danger:     bg=white, text=#dc2626, border=1px solid #fca5a5
```

- 没有渐变、没有发光、没有圆角药丸形状
- hover 状态：背景色加深一级，transition 150ms
- disabled 状态：opacity 0.5，cursor not-allowed

#### 表格

```
Header:     bg=#f9fafb, text=#6b7280, font-weight=500, font-size=12px, text-transform=uppercase
Row:        border-bottom=1px solid #f3f4f6
Row hover:  bg=#f9fafb
Cell:       padding=10px 12px, font-size=13px
```

- 去掉 Element Plus 的 striped（斑马纹）——用更轻的 hover 高亮代替
- 表头使用大写字母 + 小字号 + 灰色，降低视觉权重
- 重要性/严重性标签内联在单元格中，不用单独列

#### 标签（Tag / Badge）

```
Default:    bg=#f3f4f6, text=#3d4250, radius=2px, font-size=12px, padding=2px 6px
Success:    bg=#f0fdf4, text=#16a34a
Warning:    bg=#fefce8, text=#ca8a04
Danger:     bg=#fef2f2, text=#dc2626
Info:       bg=#f0f9ff, text=#0284c7
```

- 圆角 2px 而非 Element Plus 默认的 rounded——更方正、更专业
- 不使用深色填充标签——浅色背景 + 深色文字组合更易读

#### 卡片

```
Background: #ffffff
Border:     1px solid #e5e7eb
Radius:     4px
Padding:    16px
Shadow:     none（普通状态）/ --shadow-md（悬浮状态）
```

- 普通卡片**不加阴影**——用边框分隔
- 只有悬浮/弹出的元素才用阴影
- 不使用 Element Plus 的 `el-card`——自己用 div 实现，避免 Element Plus 的默认内边距和阴影

#### 对话气泡

```
User:       bg=#2563eb, text=white, radius=6px 6px 2px 6px
Assistant:  bg=#f3f4f6, text=#1a1d24, radius=6px 6px 6px 2px
System:     bg=#eff6ff, text=#0284c7, border-left=3px solid #2563eb, radius=0 4px 4px 0
```

- 用户气泡：实色蓝，不用渐变
- 系统消息：改为左边框强调的横条，而非气泡——系统消息是信息性的，不是"对话"
- 助手气泡：浅灰，与页面背景有区分但不抢眼

#### 进度/评分展示

Match Score 圆环：
- 不使用 Element Plus 的 `el-progress` dashboard 模式——太"仪表盘"
- 改用**横向进度条 + 数字标签**：`[████████░░] 78/100`
- 颜色映射：≥75 绿色、≥50 橙色、<50 红色
- 进度条高度 8px，radius 4px

#### Tab 切换

```
Inactive:   text=#6b7280, border-bottom=2px solid transparent
Active:     text=#1a1d24, border-bottom=2px solid #2563eb, font-weight=500
Hover:      text=#3d4250
```

- 不使用 Element Plus 的 card-style tab——太重
- 使用简洁的下划线式 tab，类似浏览器 tab 或编辑器 tab
- Tab 之间间距 24px

### Iconography

**不使用 Element Plus 的图标。**

推荐方案：**Lucide Icons**（开源，MIT 协议）
- 风格：线条图标，stroke-width 1.5px
- 尺寸：16px（内联）、20px（按钮）、24px（独立图标）
- 颜色：继承父元素 color

关键图标映射：
| 场景 | 图标 |
|------|------|
| 发送消息 | `send` |
| 上传文件 | `upload` |
| 历史记录 | `clock` |
| 设置 | `settings` |
| 导出 | `download` |
| 删除 | `trash-2` |
| 新建会话 | `plus` |
| 收起/展开 | `chevron-down` / `chevron-right` |
| 成功 | `check-circle` |
| 警告 | `alert-triangle` |
| 错误 | `x-circle` |
| 信息 | `info` |
| 难度：简单 | `circle`（空心） |
| 难度：中等 | `circle-dot` |
| 难度：困难 | `circle-filled`（实心） |
| 会话阶段 | `file-text`（有 JD）、`user`（有简历）、`git-compare`（有分析）、`file-check`（完成） |

不使用：
- 装饰性 AI / 机器人图标
- 无意义的 sparkles / magic wand 图标
- 过大的图标（>32px）

### Illustration / Graphics

**不使用插画。**

产品不插画的原因：
1. AI 生成的插画风格雷同，降低产品辨识度
2. 求职工具不需要"友好可爱"的视觉调性
3. 插画占据空间但不传递有用信息

替代方案：
- **空状态**：使用图标 + 文字引导，不用插画
- **登录页左侧**：用 CSS 生成的抽象文档线条（模拟简历/文档的排版结构），纯装饰
- **评分展示**：用数据可视化（进度条、数字）而非图形装饰

### Motion

**最小化动画。动画是功能性的，不是装饰性的。**

```
Duration:
  --duration-fast:    100ms  — 按钮 hover、颜色变化
  --duration-normal:  150ms  — 展开/折叠、tab 切换
  --duration-slow:    250ms  — drawer 滑入、modal 弹出

Easing:
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1)  — 通用
  --ease-in:      cubic-bezier(0.4, 0, 1, 1)     — 退出
  --ease-out:     cubic-bezier(0, 0, 0.2, 1)     — 进入
```

动画使用场景：
| 场景 | 动画 | 说明 |
|------|------|------|
| 新消息出现 | fade-in + 上移 4px | 150ms ease-out |
| Tab 内容切换 | crossfade | 100ms |
| Drawer 滑入 | translate-x 从右 | 250ms ease-out |
| 评分数字变化 | 数字滚动 | 300ms，仅数字部分 |
| 加载指示器 | 脉动点（···） | 不用旋转圈 |
| SSE 进度更新 | 文字替换（无动画） | 当前实现已经如此，保持 |

不使用：
- 页面转场动画
- 卡片入场的 stagger 动画
- 鼠标跟随效果
- 任何循环播放的装饰动画（除了加载指示器）

### Empty States

每种空状态都需要**具体、可操作的引导文字**，不能只是"暂无数据"。

| 场景 | 图标 | 标题 | 描述 | 行动 |
|------|------|------|------|------|
| 无会话（ChatPanel） | `message-square` | 开始新的对话 | 粘贴目标岗位的 JD，或上传简历文件 | "在下方输入框粘贴 JD，或点击 📎 上传文件" |
| 无结果（ResultPanel） | `file-text` | 等待分析结果 | 发送 JD 和简历后，分析结果将在这里展示 | — |
| 无历史记录 | `clock` | 暂无历史会话 | 开始一个新会话，完成后可在这里查看 | "新建会话" 按钮 |
| Tab 无数据（如无面试题） | 对应 tab 图标 | 面试题尚未生成 | 完成简历优化后，系统将自动生成面试准备材料 | — |

空状态视觉：
- 图标 40px，颜色 `#d1d5db`
- 标题 14px，`font-weight: 500`，`#6b7280`
- 描述 13px，`#9ca3af`
- 居中对齐，上下 padding 48px

### Loading States

**不用 Element Plus 的全屏 loading。**

| 场景 | 方案 |
|------|------|
| SSE 处理中（ChatPanel） | 助手气泡内显示脉动点 `···`，下方附当前步骤文字（如"正在分析 JD..."） |
| Result Tab 加载中 | **骨架屏（Skeleton）**：模拟内容结构的灰色矩形块，pulse 动画 |
| 页面初始加载 | Header 和侧边栏框架先渲染，内容区显示骨架屏 |
| 按钮提交中 | 按钮文字变为 "处理中..." + spinner 图标（16px），按钮禁用 |
| 历史列表加载 | 列表区域显示 3-5 行骨架条 |

骨架屏样式：
```
Background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%)
Background-size: 200% 100%
Animation: skeleton-pulse 1.5s ease-in-out infinite
Radius: 与实际内容一致
```

### Error States

**错误必须可理解、可操作。**

当前系统已有错误分类（`file_parse`、`timeout`、`rate_limit`、`auth`、`server`、`validation`、`unknown`），前端需要为每类提供友好展示：

| 错误类别 | 图标 | 标题 | 行动建议 |
|----------|------|------|----------|
| `file_parse` | `file-x` | 文件解析失败 | "请确认文件格式为 PDF/DOCX/TXT，或直接粘贴文本内容" |
| `timeout` | `clock` | 处理超时 | "服务器繁忙，请稍后重试" + 重试按钮 |
| `rate_limit` | `zap` | 请求过于频繁 | "请等待片刻后重试" + 倒计时 |
| `auth` | `lock` | 登录已过期 | "请重新登录" + 跳转按钮 |
| `server` | `server` | 服务器错误 | "服务暂时不可用，请稍后重试" + 重试按钮 |
| `validation` | `alert-triangle` | 输入格式有误 | 显示具体字段的校验提示 |
| `unknown` | `help-circle` | 未知错误 | "发生了意外错误" + 错误码 + 重试按钮 |

错误展示方式：
- ChatPanel 中：系统消息样式，红色左边框（`border-left: 3px solid #dc2626`），浅红背景
- ResultPanel 中：tab 内容区居中显示错误状态，带重试按钮
- 不使用 `ElMessage.error()` 弹出式 toast——错误信息需要持久可见，不是 3 秒消失

---

## 三、避免典型的 AI-generated UI

| AI-generated UI 特征 | 本项目的处理 |
|----------------------|-------------|
| 紫色渐变背景 | 登录页改为左图右表的白色布局，去掉 `#667eea → #764ba2` 渐变 |
| 大量圆角 Card | 卡片 radius=4px，几乎方正；能用边框分隔的不用卡片 |
| Glassmorphism | 不使用 backdrop-filter、毛玻璃效果 |
| Inter / Roboto | 使用 Noto Sans SC + IBM Plex Sans |
| 三列等宽 Card | 结果展示用 tab 切换，不用并列卡片网格 |
| 巨大的居中 Hero | 登录页用分割布局，不用居中 hero；主页直接进入工作界面 |
| 无意义的 AI 图标 | 不使用 robot、sparkles、brain 等装饰图标 |
| 到处使用渐变和阴影 | 仅按钮 hover 有微弱颜色变化，无渐变；阴影仅用于浮层 |
| 所有页面使用相同的 Dashboard 模板 | 只有 3 个页面（登录、注册、主页），各有独立布局 |

---

## 四、与当前实现的差距分析

### 需要改变的

| 当前状态 | 目标状态 | 优先级 |
|----------|----------|--------|
| Element Plus 默认主题色 `#409eff` 全局使用 | 自定义 accent `#2563eb`，仅用于关键操作引导 | P0 |
| 登录页紫色渐变背景 | 左图右表白色布局 | P0 |
| 字体栈仅 `Helvetica Neue` + 系统字体 | 引入 Noto Sans SC + IBM Plex Sans | P1 |
| `el-card` 大量使用，带默认阴影 | 自定义卡片组件，border-only，无阴影 | P1 |
| Match Score 用 `el-progress` 圆环 | 横向进度条 + 数字 | P1 |
| 无骨架屏、无加载状态区分 | 为 ResultPanel 各 tab 增加骨架屏 | P1 |
| 错误用 `ElMessage` toast | 内联错误状态展示 | P2 |
| 无 CSS 变量 / 设计 token | 建立 CSS 变量体系 | P0 |
| 空状态只有图标 + 一句话 | 增加具体引导文字和行动建议 | P2 |
| 无 Lucide Icons，使用 Element Plus Icons | 迁移到 Lucide Icons | P2 |
| `<title>` 是 "frontend" | 改为 "CareerAssistant" | P0 |
| 无 favicon | 增加 favicon | P0 |

### 可以保留的

| 当前状态 | 理由 |
|----------|------|
| 双栏分割布局（Chat + Result） | 布局合理，只需调整比例和细节 |
| SSE 流式进度消息 | 功能正确，样式调整即可 |
| Tab 切换展示 5 类结果 | 信息架构合理 |
| 消息三种视觉变体（user/assistant/system） | 概念正确，调整颜色和圆角 |
| Element Plus 表单组件 | 功能完整，样式覆盖即可 |

---

## 五、Element Plus 主题覆盖方案

通过 CSS 变量覆盖 Element Plus 默认主题，而非 fork 或替换组件库：

```css
:root {
  /* Element Plus 主题覆盖 */
  --el-color-primary: #2563eb;
  --el-color-primary-light-3: #60a5fa;
  --el-color-primary-light-5: #93bbfd;
  --el-color-primary-light-7: #bfdbfe;
  --el-color-primary-light-8: #dbeafe;
  --el-color-primary-light-9: #eff6ff;
  --el-color-primary-dark-2: #1d4ed8;

  --el-color-success: #16a34a;
  --el-color-warning: #ca8a04;
  --el-color-danger: #dc2626;
  --el-color-info: #6b7280;

  --el-border-radius-base: 4px;
  --el-border-radius-small: 2px;
  --el-border-radius-round: 9999px;

  --el-font-family: 'Noto Sans SC', 'IBM Plex Sans', 'Helvetica Neue', sans-serif;
  --el-font-size-base: 14px;

  --el-border-color: #e5e7eb;
  --el-border-color-light: #f3f4f6;
  --el-bg-color-page: #f9fafb;
  --el-text-color-primary: #1a1d24;
  --el-text-color-regular: #3d4250;
  --el-text-color-secondary: #6b7280;
  --el-text-color-placeholder: #9ca3af;
  --el-fill-color-light: #f9fafb;
}
```

这种方式：
- 零破坏性——Element Plus 组件保持原样，只换肤
- 全局生效——一处定义，所有组件跟随
- 易维护——设计 token 集中管理

---

## 六、字体加载策略

```html
<!-- index.html <head> 中添加 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;600&family=Noto+Serif+SC:wght@400;600&display=swap" rel="stylesheet">
```

备选方案（如 Google Fonts 不可用）：
- 将字体文件放在 `frontend/public/fonts/` 下，使用 `@font-face` 自托管
- Noto Sans SC 子集化（只包含常用汉字 + 拉丁字符），控制文件大小

---

## 七、实施优先级

### Phase 1：基础设计系统（P0）
1. 创建 `src/styles/tokens.css`——所有 CSS 变量
2. Element Plus 主题覆盖
3. 全局字体引入
4. 修复 `<title>` 和 favicon

### Phase 2：核心组件重塑（P1）
1. 登录/注册页重新设计
2. 卡片、标签、按钮样式覆盖
3. Match Score 从圆环改为横向进度条
4. 骨架屏组件

### Phase 3：体验细节（P2）
1. 空状态优化
2. 错误状态内联展示
3. 图标迁移到 Lucide
4. 动画微调

---

## 八、设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| CSS 方案 | CSS 变量 + Element Plus 覆盖 | 最小改动，最大效果；不引入 Tailwind 增加构建复杂度 |
| 字体 | Noto Sans SC + IBM Plex Sans | 免费、专业、屏幕渲染优秀、有辨识度 |
| 主题色 | `#2563eb`（蓝色） | 职业场景的信任色；远离 AI 产品的紫色刻板印象 |
| 圆角策略 | 小圆角（2-4px） | 传达专业、精确，不追求"可爱" |
| 阴影策略 | 仅浮层使用 | 文档工具不需要"浮起"的感觉 |
| 插画 | 不使用 | 不增加信息密度，且 AI 插画风格雷同 |
| 图标库 | Lucide Icons | 开源、风格统一、与线条型 UI 协调 |
| 移动端 | 不考虑 | 求职准备是桌面场景，移动端体验无法保证 |
