# 个人知识库分阶段表单契约

> 文档类型：前后端对接契约
> 对应阶段：阶段3「知识库分阶段结构化表单」(2026-09-07)
> 上游参考：`逆向工程/FResume项目截图及部分说明/01_用户信息初始化/*.png`

## 1. 背景

知识库「补充知识库」由通用 4 字段弹窗（分类/标题/内容/类型）升级为 **FResume 风格分阶段向导**。
表单数据写入现有 `profile_items` 表，**标题与下游 `aggregate_confirmed_profile` 及简历生成「从知识库导入」读取的标题完全一致**，
从而保证方向推荐 / 软性信息 / 简历生成正确复用。

## 2. 阶段（前端向导 6 步）

| 步 | 阶段 | 字段 | 写入分类 |
|---|---|---|---|
| 01 | 基本信息 | 姓名/手机/邮箱/所在地点/性别/出生日期/国籍/家乡 | `basic_info` |
| 02 | 教育经历 | 学校/学历/专业/主修课程/开始时间/结束时间/GPA（可多条） | `education` |
| 03 | 个人奖项 | 多行文本（每行一条） | `award` |
| 04 | 社交账号 | 平台/账号（可多条） | `social` |
| 05 | 个人头像 | 上传（JPG/PNG/WEBP，居中裁剪 256×256） | `resume_photos`（复用） |
| 06 | 其他画像 | 分类 + 标题 + 内容 | `experience`/`skill`/`target`/`soft`/`interview_feedback` |

## 3. 基本信息字段 → 条目标题 映射

写出的 `basic_info` 条目标题必须为（`profile_form_service.BASIC_INFO_FIELDS`）：

| 表单键 | profile_items.title | 下游识别 |
|---|---|---|
| name | 姓名 | → `name` |
| phone | 电话 | → `phone` |
| email | 邮箱 | → `email` |
| location | 所在地 | → `location` |
| gender | 性别 | 简历生成导入 |
| birthday | 出生日期 | 简历生成导入 |
| nationality | 国籍 | — |
| hometown | 家乡 | — |

> 注意：表单 label 用「手机 / 所在地点」，但写入 title 是「电话 / 所在地」，与下游一致。

## 4. 后端接口

### `GET /api/profile/form`
返回 `ProfileFormOut`（回显/继续编辑）：

```json
{
  "basic_info": {"name": "栗子", "phone": "19823342343", "email": "2378166881@qq.com", "location": "北京", "gender": "男", "birthday": "2004-04-08", "nationality": "中国", "hometown": "北京"},
  "education": [{"school": "北京交通大学", "degree": "本科", "major": "软件工程", "courses": "数据结构", "start": "2020-09", "end": "2024-06", "gpa": "3.8"}],
  "awards": ["国家奖学金", "数学竞赛一等奖"],
  "social": [{"platform": "QQ", "account": "2323613122"}],
  "extra": [{"category": "experience", "title": "arXiv 问答系统", "content": "RAG 全链路"}]
}
```

### `POST /api/profile/form`
Body = `ProfileFormSave`（`basic_info` 对象 / `education` 数组 / `awards` 字符串(多行) / `social` 数组 / `extra` 数组）。
幂等 upsert（按 category+title），重复保存不产生重复条目；返回保存后的 `ProfileFormOut`。

## 5. 数据联动

- `aggregate_confirmed_profile` 新增：`award` → `certifications`；`social` → `social`。
- 方向推荐/软性信息 `_format_profile` 新增输出 `证书/奖项`、`社交账号`。
- 简历生成「从知识库导入」新增：`award` 内容按行 → 证书；`出生日期` 映射。
- 个人头像与简历证件照共用 `resume_photos`（一次输入多处复用）。

## 6. 前端接线

- `components/ProfileFormWizard.vue`（v-model 开合，`@saved` 后刷新 store 与头像）。
- `KnowledgeBaseView.vue`：旧 `el-dialog` 替换为 `<ProfileFormWizard>`；节点图中央显示头像。
- `api/profile.ts`：`getProfileForm()` / `saveProfileForm(data)`。
- `types/index.ts`：`ProfileCategory` 增 `award`/`social`；新增 `ProfileFormData/ProfileFormSave/ProfileEducationEntry/ProfileSocialEntry/ProfileExtraEntry`。
