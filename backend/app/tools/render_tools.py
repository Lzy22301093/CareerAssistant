"""内容生成工具：html_renderer, template_search。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Tool, ToolResult


class HtmlRendererTool(Tool):
    """HTML 渲染工具 — 使用 Jinja2 生成 HTML。"""

    name = "html_renderer"
    description = "使用模板渲染 HTML 简历。"
    parameters = {
        "type": "object",
        "properties": {
            "template_name": {
                "type": "string",
                "description": "模板名称（如 'modern', 'classic', 'minimal'）",
            },
            "data": {
                "type": "object",
                "description": "模板数据（包含简历内容）",
            },
        },
        "required": ["template_name", "data"],
    }

    # 模板目录
    _TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

    def __init__(self):
        from jinja2 import Environment, FileSystemLoader

        self._env = Environment(
            loader=FileSystemLoader(str(self._TEMPLATE_DIR)),
            autoescape=True,
        )
        # 确保模板目录存在
        self._TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        self._create_default_templates()

    async def execute(
        self,
        template_name: str,
        data: dict[str, Any],
        **kwargs,
    ) -> ToolResult:
        """渲染 HTML。"""
        try:
            template_file = f"{template_name}.html"
            template = self._env.get_template(template_file)
            html = template.render(**data)
            return ToolResult.ok({"html": html, "template": template_name})
        except Exception as e:
            return ToolResult.fail(f"HTML 渲染失败: {e}")

    def _create_default_templates(self):
        """创建默认模板（如果不存在）。"""
        templates = {
            "modern": self._modern_template(),
            "classic": self._classic_template(),
            "minimal": self._minimal_template(),
        }

        for name, content in templates.items():
            template_path = self._TEMPLATE_DIR / f"{name}.html"
            if not template_path.exists():
                template_path.write_text(content, encoding="utf-8")

    def _modern_template(self) -> str:
        """现代风格模板。"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ name }} - 简历</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 40px; color: #333; }
        .header { border-bottom: 3px solid #2c3e50; padding-bottom: 20px; margin-bottom: 30px; }
        .name { font-size: 32px; color: #2c3e50; margin: 0; }
        .contact { color: #7f8c8d; margin-top: 10px; }
        .section { margin-bottom: 30px; }
        .section-title { font-size: 20px; color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }
        .item { margin: 15px 0; }
        .item-header { display: flex; justify-content: space-between; font-weight: bold; }
        .item-date { color: #7f8c8d; }
        .skills { display: flex; flex-wrap: wrap; gap: 10px; }
        .skill-tag { background: #ecf0f1; padding: 5px 15px; border-radius: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="name">{{ name }}</h1>
        <div class="contact">
            {% if email %}📧 {{ email }}{% endif %}
            {% if phone %} | 📱 {{ phone }}{% endif %}
            {% if location %} | 📍 {{ location }}{% endif %}
        </div>
    </div>

    {% if summary %}
    <div class="section">
        <h2 class="section-title">个人简介</h2>
        <p>{{ summary }}</p>
    </div>
    {% endif %}

    {% if skills %}
    <div class="section">
        <h2 class="section-title">专业技能</h2>
        <div class="skills">
            {% for skill in skills %}
            <span class="skill-tag">{{ skill }}</span>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    {% if experience %}
    <div class="section">
        <h2 class="section-title">工作经历</h2>
        {% for exp in experience %}
        <div class="item">
            <div class="item-header">
                <span>{{ exp.title }} - {{ exp.company }}</span>
                <span class="item-date">{{ exp.date }}</span>
            </div>
            <p>{{ exp.description }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if education %}
    <div class="section">
        <h2 class="section-title">教育背景</h2>
        {% for edu in education %}
        <div class="item">
            <div class="item-header">
                <span>{{ edu.school }}</span>
                <span class="item-date">{{ edu.date }}</span>
            </div>
            <p>{{ edu.degree }} - {{ edu.major }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if projects %}
    <div class="section">
        <h2 class="section-title">项目经验</h2>
        {% for proj in projects %}
        <div class="item">
            <div class="item-header">
                <span>{{ proj.name }}</span>
                <span class="item-date">{{ proj.date }}</span>
            </div>
            <p>{{ proj.description }}</p>
            {% if proj.technologies %}
            <p><strong>技术栈：</strong>{{ proj.technologies | join(', ') }}</p>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endif %}
</body>
</html>'''

    def _classic_template(self) -> str:
        """经典风格模板。"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ name }} - 简历</title>
    <style>
        body { font-family: 'Times New Roman', serif; margin: 40px; color: #000; }
        .header { text-align: center; margin-bottom: 30px; }
        .name { font-size: 28px; margin: 0; }
        .contact { margin-top: 10px; }
        .section { margin-bottom: 25px; }
        .section-title { font-size: 16px; text-transform: uppercase; border-bottom: 1px solid #000; padding-bottom: 3px; }
        .item { margin: 12px 0; }
        .item-header { font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="name">{{ name }}</h1>
        <div class="contact">
            {% if email %}{{ email }}{% endif %}
            {% if phone %} | {{ phone }}{% endif %}
            {% if location %} | {{ location }}{% endif %}
        </div>
    </div>

    {% if summary %}
    <div class="section">
        <h2 class="section-title">Summary</h2>
        <p>{{ summary }}</p>
    </div>
    {% endif %}

    {% if skills %}
    <div class="section">
        <h2 class="section-title">Skills</h2>
        <p>{{ skills | join(' • ') }}</p>
    </div>
    {% endif %}

    {% if experience %}
    <div class="section">
        <h2 class="section-title">Experience</h2>
        {% for exp in experience %}
        <div class="item">
            <div class="item-header">{{ exp.title }}, {{ exp.company }} ({{ exp.date }})</div>
            <p>{{ exp.description }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if education %}
    <div class="section">
        <h2 class="section-title">Education</h2>
        {% for edu in education %}
        <div class="item">
            <div class="item-header">{{ edu.school }} ({{ edu.date }})</div>
            <p>{{ edu.degree }} - {{ edu.major }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</body>
</html>'''

    def _minimal_template(self) -> str:
        """极简风格模板。"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ name }} - 简历</title>
    <style>
        body { font-family: 'Helvetica Neue', sans-serif; margin: 50px; color: #333; line-height: 1.6; }
        h1 { font-size: 24px; font-weight: 300; }
        .contact { color: #666; font-size: 14px; margin-bottom: 40px; }
        .section { margin-bottom: 35px; }
        .section-title { font-size: 14px; text-transform: uppercase; letter-spacing: 2px; color: #999; margin-bottom: 15px; }
        .item { margin-bottom: 20px; }
        .item-title { font-weight: 500; }
        .item-meta { font-size: 14px; color: #666; }
    </style>
</head>
<body>
    <h1>{{ name }}</h1>
    <div class="contact">
        {% if email %}{{ email }}{% endif %}
        {% if phone %} · {{ phone }}{% endif %}
        {% if location %} · {{ location }}{% endif %}
    </div>

    {% if summary %}
    <div class="section">
        <div class="section-title">About</div>
        <p>{{ summary }}</p>
    </div>
    {% endif %}

    {% if skills %}
    <div class="section">
        <div class="section-title">Skills</div>
        <p>{{ skills | join(' · ') }}</p>
    </div>
    {% endif %}

    {% if experience %}
    <div class="section">
        <div class="section-title">Experience</div>
        {% for exp in experience %}
        <div class="item">
            <div class="item-title">{{ exp.title }} at {{ exp.company }}</div>
            <div class="item-meta">{{ exp.date }}</div>
            <p>{{ exp.description }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if education %}
    <div class="section">
        <div class="section-title">Education</div>
        {% for edu in education %}
        <div class="item">
            <div class="item-title">{{ edu.school }}</div>
            <div class="item-meta">{{ edu.degree }} · {{ edu.major }} · {{ edu.date }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</body>
</html>'''


class TemplateSearchTool(Tool):
    """模板搜索工具 — 搜索可用的简历模板。"""

    name = "template_search"
    description = "搜索可用的简历模板，返回模板列表和预览信息。"
    parameters = {
        "type": "object",
        "properties": {
            "style": {
                "type": "string",
                "enum": ["modern", "classic", "minimal", "all"],
                "description": "模板风格筛选",
            },
        },
        "required": [],
    }

    # 模板元数据
    _TEMPLATES = [
        {
            "name": "modern",
            "display_name": "现代风格",
            "description": "简洁现代的设计，适合科技、互联网行业",
            "style": "modern",
            "preview_color": "#2c3e50",
        },
        {
            "name": "classic",
            "display_name": "经典风格",
            "description": "传统正式的设计，适合金融、法律等行业",
            "style": "classic",
            "preview_color": "#000000",
        },
        {
            "name": "minimal",
            "display_name": "极简风格",
            "description": "极简主义设计，适合设计、创意行业",
            "style": "minimal",
            "preview_color": "#999999",
        },
    ]

    async def execute(self, style: str = "all", **kwargs) -> ToolResult:
        """搜索模板。"""
        try:
            if style == "all":
                templates = self._TEMPLATES
            else:
                templates = [t for t in self._TEMPLATES if t["style"] == style]

            return ToolResult.ok({"templates": templates, "count": len(templates)})
        except Exception as e:
            return ToolResult.fail(f"模板搜索失败: {e}")
