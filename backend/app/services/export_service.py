"""导出服务 — 负责简历导出（HTML/JSON/Markdown）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.schemas import ResumeContent


class ExportService:
    """导出服务。

    职责：
    - 导出 HTML 简历
    - 导出 JSON 数据
    - 导出 Markdown 文本
    """

    def __init__(self, output_dir: str = "exports"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def export_html(
        self, html: str, session_id: str, filename: str | None = None
    ) -> str:
        """导出 HTML 文件。"""
        name = filename or f"resume_{session_id}.html"
        file_path = self._output_dir / name
        file_path.write_text(html, encoding="utf-8")
        return str(file_path)

    async def export_json(
        self, content: dict, session_id: str, filename: str | None = None
    ) -> str:
        """导出 JSON 文件。"""
        name = filename or f"resume_{session_id}.json"
        file_path = self._output_dir / name
        file_path.write_text(
            json.dumps(content, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(file_path)

    async def export_markdown(
        self, content: dict, session_id: str, filename: str | None = None
    ) -> str:
        """导出 Markdown 文件。"""
        name = filename or f"resume_{session_id}.md"
        file_path = self._output_dir / name

        md_text = self._to_markdown(content)
        file_path.write_text(md_text, encoding="utf-8")
        return str(file_path)

    def _to_markdown(self, content: dict) -> str:
        """将简历内容转换为 Markdown。"""
        lines = []

        # 标题
        profile = content.get("profile", {})
        if profile.get("name"):
            lines.append(f"# {profile['name']}")
            lines.append("")

        # 联系方式
        contact_parts = []
        if profile.get("email"):
            contact_parts.append(f"📧 {profile['email']}")
        if profile.get("phone"):
            contact_parts.append(f"📱 {profile['phone']}")
        if profile.get("location"):
            contact_parts.append(f"📍 {profile['location']}")
        if contact_parts:
            lines.append(" | ".join(contact_parts))
            lines.append("")

        # 各部分
        sections = content.get("sections", [])
        for section in sections:
            title = section.get("title", "")
            section_content = section.get("content", "")

            lines.append(f"## {title}")
            lines.append("")
            lines.append(section_content)
            lines.append("")

        return "\n".join(lines)

    async def export(
        self,
        format: str,
        content: dict,
        html: str,
        session_id: str,
    ) -> dict[str, Any]:
        """统一导出接口。

        Args:
            format: 导出格式 (html/json/markdown)
            content: 简历内容数据
            html: HTML 内容
            session_id: 会话 ID

        Returns:
            包含 file_path 和 format 的字典
        """
        if format == "html":
            path = await self.export_html(html, session_id)
        elif format == "json":
            path = await self.export_json(content, session_id)
        elif format == "markdown":
            path = await self.export_markdown(content, session_id)
        else:
            raise ValueError(f"不支持的导出格式: {format}")

        return {
            "file_path": path,
            "format": format,
            "session_id": session_id,
        }
