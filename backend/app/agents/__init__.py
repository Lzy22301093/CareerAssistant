"""Agents 包 — 简历助手 Agent 集合。"""

from app.agents.base import BaseAgent
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.profile_extractor import ProfileExtractorAgent
from app.agents.gap_analyzer import GapAnalyzerAgent
from app.agents.content_generator import ContentGeneratorAgent
from app.agents.html_renderer import HTMLRendererAgent
from app.agents.interview_qa import InterviewQAAgent
from app.agents.interview_reviewer import InterviewReviewerAgent
from app.agents.planner import PlannerAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.clarifier import ClarifierAgent
from app.agents.question import QuestionAgent
from app.agents.cover_letter import CoverLetterAgent

__all__ = [
    "BaseAgent",
    "JDAnalyzerAgent",
    "ProfileExtractorAgent",
    "GapAnalyzerAgent",
    "ContentGeneratorAgent",
    "HTMLRendererAgent",
    "InterviewQAAgent",
    "InterviewReviewerAgent",
    "PlannerAgent",
    "ReviewerAgent",
    "ClarifierAgent",
    "QuestionAgent",
    "CoverLetterAgent",
    "create_agents",
]


def create_agents(llm) -> dict[str, BaseAgent]:
    """创建所有 Agent 实例。

    部分 Agent 注册了工具（function calling）：
    - gap_analyzer: similar_cases（RAG 相似案例检索）
    - interview_qa: question_bank（面试题库检索）
    - content_generator: best_practices / keyword_optimizer / template_search

    模型分层（性能优化）：
    - 提取/评审/澄清类 Agent 使用快速模型（settings.fast_model，未配置则回退主模型），
      低 temperature + 小 max_tokens，任务简单但调用频繁
    - 生成类 Agent 使用主模型，保证内容质量

    Args:
        llm: LLMProvider 实例。

    Returns:
        字典，键为 Agent 名称，值为 Agent 实例。
    """
    # 工具与配置在函数内延迟导入，避免模块加载时的循环依赖和开销
    from app.config import settings
    from app.rag.service import RAGService
    from app.tools.analysis_tools import BestPracticesTool, KeywordOptimizerTool, SimilarCasesTool
    from app.tools.knowledge_tools import QuestionBankTool
    from app.tools.render_tools import TemplateSearchTool

    fast_model = settings.fast_model or None

    return {
        "jd_analyzer": JDAnalyzerAgent(llm, model=fast_model),
        "profile_extractor": ProfileExtractorAgent(llm, model=fast_model),
        "gap_analyzer": GapAnalyzerAgent(
            llm,
            tools=[SimilarCasesTool(rag_service=RAGService())],
            model=fast_model,
        ),
        "content_generator": ContentGeneratorAgent(
            llm,
            tools=[
                BestPracticesTool(),
                KeywordOptimizerTool(),
                TemplateSearchTool(),
            ],
        ),
        "html_renderer": HTMLRendererAgent(llm),
        "interview_qa": InterviewQAAgent(
            llm,
            tools=[QuestionBankTool(llm_provider=llm)],
        ),
        "interview_reviewer": InterviewReviewerAgent(llm, model=fast_model),
        "planner": PlannerAgent(llm),
        "reviewer": ReviewerAgent(llm, model=fast_model),
        "clarifier": ClarifierAgent(llm, model=fast_model),
        "question": QuestionAgent(llm, model=fast_model),
        "cover_letter": CoverLetterAgent(llm),
    }
