"""RAG Service — 检索增强生成服务。"""

from __future__ import annotations

import logging
from typing import Any

from app.rag.embedding import EmbeddingService
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 服务：结合检索和生成，提供相似案例参考。"""

    def __init__(
        self,
        embedding_service: EmbeddingService = None,
        vector_store: VectorStore = None,
    ) -> None:
        self._embedding = embedding_service or EmbeddingService()
        self._store = vector_store or VectorStore()

    def add_case(
        self,
        case_id: str,
        content: str,
        metadata: dict[str, Any] = None,
    ) -> None:
        """添加案例到知识库。"""
        embedding = self._embedding.embed(content)
        self._store.add(
            ids=[case_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata or {}],
        )
        logger.info(f"Added case: {case_id}")

    def add_cases_batch(
        self,
        case_ids: list[str],
        contents: list[str],
        metadatas: list[dict[str, Any]] = None,
    ) -> None:
        """批量添加案例。"""
        embeddings = self._embedding.embed_batch(contents)
        self._store.add(
            ids=case_ids,
            documents=contents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(case_ids)} cases")

    def search_similar(
        self,
        query: str,
        n_results: int = 5,
        category: str = None,
    ) -> list[dict[str, Any]]:
        """搜索相似案例。"""
        query_embedding = self._embedding.embed(query)
        where = {"category": category} if category else None
        results = self._store.query(
            query_embedding=query_embedding,
            n_results=n_results,
            where=where,
        )
        # 格式化结果
        cases = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"][0]):
                cases.append({
                    "id": doc_id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "similarity": 1 - results["distances"][0][i] if results.get("distances") else 0,
                })
        return cases

    def get_context_for_resume(
        self,
        job_title: str,
        skills: list[str],
        n_results: int = 3,
    ) -> str:
        """为简历生成获取参考案例上下文。"""
        query = f"{job_title} {' '.join(skills)}"
        cases = self.search_similar(query, n_results=n_results, category="resume")
        if not cases:
            return ""
        context_parts = ["参考案例："]
        for i, case in enumerate(cases, 1):
            context_parts.append(f"\n--- 案例 {i} (相似度: {case['similarity']:.2f}) ---")
            context_parts.append(case["content"][:500])
        return "\n".join(context_parts)

    def get_context_for_interview(
        self,
        job_title: str,
        skills: list[str],
        n_results: int = 3,
    ) -> str:
        """为面试题生成获取参考案例上下文。"""
        query = f"{job_title} 面试 {' '.join(skills)}"
        cases = self.search_similar(query, n_results=n_results, category="interview")
        if not cases:
            return ""
        context_parts = ["参考面试题："]
        for i, case in enumerate(cases, 1):
            context_parts.append(f"\n--- 题目 {i} ---")
            context_parts.append(case["content"][:300])
        return "\n".join(context_parts)
