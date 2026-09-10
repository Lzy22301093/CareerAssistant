# CareerAssistant 前端设计规范（Claude 风格）

> 本文件是前端重设计的**唯一视觉契约**。所有页面/组件/样式都必须遵循本规范。
> 视觉 token 统一定义在 `src/styles/tokens.css`，Element Plus 覆盖在 `src/styles/element-overrides.css`，其余只读这两层。
> 参考：Claude 官网 · FResume 参考产品截图（`逆向工程/`）

---

## 1. 风格基调

- **背景**：暖米色纸感（`--color-bg-page`，非冷灰）。
- **标题**：衬线体（`--font-display` = Noto Serif SC），有编辑感、呼吸感。
- **强调色**：陶土橙/珊瑚（`--color-accent-600` = `#c15f3c`），代替原来的冷蓝。
- **组件**：圆润（`--radius-md/lg`）、暖白卡（`--color-bg`）、柔和阴影（`--shadow-card`）、充足留白、克制边框。
- 界面应像一份精美的简历/文档，而不是后台管理台报表。

## 2. 色彩规范

### 中性色（暖米灰）
| Token | 说明 |
|---|---|
| `--color-gray-900` | 主要文字 |
| `--color-gray-700` | 次要文字 |
| `--color-gray-500` | 辅助文字/占位 |
| `--color-gray-400` | 禁用 |
| `--color-gray-300` | 强边框 |
| `--color-gray-200` | 常规边框/分割线 |
| `--color-gray-100` | hover 背景 |
| `--color-gray-50` | 页面背景 |

### 强调色（陶土橙）
`--color-accent-600`(主) / `--color-accent-500`(hover) / `--color-accent-400` / `--color-accent-200`(焦点环) / `--color-accent-100`(浅底) / `--color-accent-50`(极浅底)。别名 `--color-primary-*` 映射到 accent。

### 语义色（暖调）
`--color-success-600` / `--color-warning-600` / `--color-danger-600` / `--color-info-600`，各对应 `-50` 浅底。

### 禁用
**禁止在组件里硬编码任何 hex 色值**（尤其蓝色系 `#2563eb/#3b82f6/#60a5fa/#eff6ff/#93c5fd/#c7d2fe/#f9fafb/#9ca3af/#dc2626` 等）。一律引用上述 token；需要变体就用 `color-mix(in srgb, var(--color-accent-600) N%, transparent/white)`。
**禁止用 emoji 当图标**，一律用 `lucide-vue-next`。

## 3. 字体规范

- 页面/板块标题：`font-family: var(--font-display)`（衬线）。
- 正文：`var(--font-sans)`。代码：`var(--font-mono)`。
- 字号：页面级标题 `--text-xl/~2xl`；板块标题 `--text-md/~lg` + `--weight-semibold`；正文 `--text-sm/~base`。
- 大 Hero 可用 `--text-3xl/~4xl`，配合 `letter-spacing:-0.02em`。

## 4. 圆角 / 阴影 / 间距

- 圆角：按钮/输入 `--radius-sm`(6)，卡片/面板 `--radius-md`(10)，主卡/弹窗 `--radius-lg`(14)，圆形 `--radius-full`。
- 阴影：卡片 `--shadow-card`，悬浮 `--shadow-md`，模态 `--shadow-lg`。
- 间距：4px 基准，用 `--space-*`（`--space-1..16`）。
- 边框：`--border-light` / `--border-medium`，颜色统一走 token。

## 5. 卡片 / 布局规范

- 卡片：`background: var(--color-bg-elevated)` + `border: var(--border-light)` + `border-radius: var(--radius-lg)` + `box-shadow: var(--shadow-card)`；hover 可 `translateY(-2px)` + `--shadow-md`，边框转 accent。
- 列表卡片可加左侧 4px 强调条 `--accent`（彩色），仿参考产品的彩色强调条。
- 图标 tile：`width/height: 40~44px; border-radius: var(--radius-md); background: color-mix(in srgb, var(--color-accent-600) 14%, white); color: var(--color-accent-600)`。

## 6. 四态规范（每个界面必须）

任何数据驱动的界面都必须呈现一致的四种状态：

1. **loading**：统一用 `SkeletonLoader`（`variant=text/card/table/chart`）；长时间任务用明确进度/文案，不等同于按钮转圈。
2. **empty**：统一空态（`el-empty` 或自绘，用 token + lucide 图标 + 主动作引导）。
3. **error**：统一错误提示，语义色 `--color-danger-*`（`el-alert` 或自绘），文案中文、可读、可重试。
4. **data**：正常内容，层级清晰、衬线标题、呼吸感行距。

不要让同一页面出现"`v-loading` + 自绘 spinner + 骨架屏"多重不一致的加载。删除/破坏性操作要有确认；长任务要有"提交后进入后台/轮询"的状态反馈。

## 7. 交互一致性

- 破坏性操作二次确认；成功的删除可考虑撤销提示。
- 表单提交：`loading` 按钮 + 禁用重复提交 + 成功/失败 `ElMessage` / inline error。
- 会话/状态切换后，**重置相关临时选中态**（如切换文档/版本后清空选中区域对话）。
- 每个按钮/可交互元素有 hover/focus/active 态（focus 用 `--color-accent-200` 焦点环）。

## 8. 验证

改完必须 `npx vue-tsc --noEmit` 通过 + `npm run build` 通过；**不修改**任意 API 函数签名、store state/action、props/emits、路由、后端契约。
