"""Tools 包 — Agent 工具集。"""

from .base import Tool, ToolResult
from .file_tools import FileParserTool, TextCleanerTool
from .extract_tools import EntityExtractorTool, KeywordExtractorTool
from .render_tools import HtmlRendererTool, TemplateSearchTool
from .knowledge_tools import QuestionBankTool, IndustryStandardsTool
from .state_tools import StateReaderTool, StateWriterTool

__all__ = [
    # 基类
    "Tool",
    "ToolResult",
    # 文件处理
    "FileParserTool",
    "TextCleanerTool",
    # 信息提取
    "EntityExtractorTool",
    "KeywordExtractorTool",
    # 内容生成
    "HtmlRendererTool",
    "TemplateSearchTool",
    # 知识检索
    "QuestionBankTool",
    "IndustryStandardsTool",
    # 状态管理
    "StateReaderTool",
    "StateWriterTool",
]


def create_all_tools(llm_provider=None, session_store=None, db_session=None) -> list[Tool]:
    """创建所有工具实例。"""
    return [
        # 文件处理
        FileParserTool(),
        TextCleanerTool(),
        # 信息提取（需要 LLM）
        EntityExtractorTool(llm_provider=llm_provider),
        KeywordExtractorTool(llm_provider=llm_provider),
        # 内容生成
        HtmlRendererTool(),
        TemplateSearchTool(),
        # 知识检索（需要 LLM）
        QuestionBankTool(llm_provider=llm_provider),
        IndustryStandardsTool(llm_provider=llm_provider),
        # 状态管理（需要存储）
        StateReaderTool(session_store=session_store, db_session=db_session),
        StateWriterTool(session_store=session_store, db_session=db_session),
    ]
