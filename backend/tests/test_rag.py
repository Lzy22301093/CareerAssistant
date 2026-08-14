"""RAG 服务测试。"""

from __future__ import annotations

import pytest

from app.rag.embedding import EmbeddingService
from app.rag.vector_store import VectorStore, InMemoryCollection
from app.rag.service import RAGService


# === EmbeddingService 测试 ===


class TestEmbeddingService:
    def test_embed_returns_vector(self):
        """embed 返回向量。"""
        service = EmbeddingService()
        vector = service.embed("Python 工程师")
        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(v, float) for v in vector)

    def test_embed_consistent(self):
        """相同文本返回相同向量。"""
        service = EmbeddingService()
        v1 = service.embed("Python")
        v2 = service.embed("Python")
        assert v1 == v2

    def test_embed_different_texts(self):
        """不同文本返回不同向量。"""
        service = EmbeddingService()
        v1 = service.embed("Python")
        v2 = service.embed("Java")
        assert v1 != v2

    def test_embed_batch(self):
        """批量 embed。"""
        service = EmbeddingService()
        vectors = service.embed_batch(["Python", "Java", "Go"])
        assert len(vectors) == 3
        assert all(len(v) > 0 for v in vectors)

    def test_dimension(self):
        """向量维度。"""
        service = EmbeddingService()
        dim = service.dimension
        assert dim > 0


# === InMemoryCollection 测试 ===


class TestInMemoryCollection:
    def test_add_and_query(self):
        """添加并查询。"""
        collection = InMemoryCollection()
        collection.add(
            ids=["1", "2"],
            documents=["Python 工程师", "Java 工程师"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        )
        assert collection.count() == 2

    def test_delete(self):
        """删除文档。"""
        collection = InMemoryCollection()
        collection.add(ids=["1"], documents=["test"], embeddings=[[1.0]])
        collection.delete(["1"])
        assert collection.count() == 0

    def test_query_similarity(self):
        """相似度查询。"""
        collection = InMemoryCollection()
        collection.add(
            ids=["1", "2", "3"],
            documents=["Python 高级工程师", "Java 开发", "Python 初级"],
            embeddings=[[1.0, 0.0], [0.0, 1.0], [0.8, 0.6]],
        )
        results = collection.query(
            query_embeddings=[[1.0, 0.0]],
            n_results=2,
        )
        assert len(results["ids"][0]) == 2
        assert results["ids"][0][0] == "1"  # 最相似


# === VectorStore 测试 ===


class TestVectorStore:
    def test_add_and_count(self):
        """添加并计数。"""
        store = VectorStore()
        store.add(
            ids=["case-1"],
            documents=["Python 工程师 3 年经验"],
            embeddings=[[1.0, 0.0, 0.0]],
        )
        assert store.count() == 1

    def test_query(self):
        """查询。"""
        store = VectorStore()
        store.add(
            ids=["case-1", "case-2"],
            documents=["Python 工程师", "Java 工程师"],
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
        )
        results = store.query(query_embedding=[1.0, 0.0], n_results=1)
        assert results["ids"][0][0] == "case-1"


# === RAGService 测试 ===


class TestRAGService:
    def test_add_and_search(self):
        """添加案例并搜索。"""
        service = RAGService()
        service.add_case(
            case_id="resume-1",
            content="Python 高级工程师，5 年经验，精通 FastAPI 和 Django",
            metadata={"category": "resume", "job_title": "Python 工程师"},
        )
        service.add_case(
            case_id="resume-2",
            content="Java 开发工程师，3 年经验，Spring Boot",
            metadata={"category": "resume", "job_title": "Java 工程师"},
        )
        results = service.search_similar("Python 后端开发", n_results=2)
        assert len(results) == 2
        # 注意：使用 dummy embedding 时不保证排序，只验证返回结构
        assert all("id" in r and "content" in r and "similarity" in r for r in results)

    def test_search_with_category(self):
        """按类别搜索。"""
        service = RAGService()
        service.add_case("r1", "Python 简历", {"category": "resume"})
        service.add_case("i1", "Python 面试题", {"category": "interview"})
        results = service.search_similar("Python", category="resume", n_results=5)
        assert all(r["metadata"].get("category") == "resume" for r in results)

    def test_get_context_for_resume(self):
        """获取简历参考上下文。"""
        service = RAGService()
        service.add_case(
            "r1",
            "Python 高级工程师简历示例，包含 FastAPI 项目经验",
            {"category": "resume"},
        )
        context = service.get_context_for_resume("Python 工程师", ["FastAPI", "Django"])
        assert "参考案例" in context
        assert "Python" in context

    def test_get_context_for_interview(self):
        """获取面试参考上下文。"""
        service = RAGService()
        service.add_case(
            "i1",
            "Python 面试题：请介绍 GIL",
            {"category": "interview"},
        )
        context = service.get_context_for_interview("Python 工程师", ["Python"])
        assert "参考面试题" in context

    def test_add_cases_batch(self):
        """批量添加案例。"""
        service = RAGService()
        service.add_cases_batch(
            case_ids=["b1", "b2", "b3"],
            contents=["案例1", "案例2", "案例3"],
            metadatas=[{"category": "resume"}] * 3,
        )
        assert service._store.count() == 3
