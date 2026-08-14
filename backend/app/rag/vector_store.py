"""Vector Store — ChromaDB 向量存储。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB 向量存储，用于检索相似案例。"""

    def __init__(self, collection_name: str = "career_cases", persist_directory: str = None) -> None:
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._client = None
        self._collection = None

    def _get_collection(self):
        """延迟初始化 ChromaDB。"""
        if self._collection is None:
            try:
                import chromadb
                if self._persist_directory:
                    self._client = chromadb.PersistentClient(path=self._persist_directory)
                else:
                    self._client = chromadb.Client()
                self._collection = self._client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"ChromaDB collection '{self._collection_name}' ready")
            except ImportError:
                logger.warning("chromadb not available, using in-memory store")
                self._collection = InMemoryCollection()
        return self._collection

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] = None,
    ) -> None:
        """添加文档到向量存储。"""
        collection = self._get_collection()
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict = None,
    ) -> dict[str, Any]:
        """查询相似文档。"""
        collection = self._get_collection()
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def delete(self, ids: list[str]) -> None:
        """删除文档。"""
        collection = self._get_collection()
        collection.delete(ids=ids)

    def count(self) -> int:
        """返回文档数量。"""
        collection = self._get_collection()
        return collection.count()


class InMemoryCollection:
    """内存向量集合（ChromaDB 不可用时的降级方案）。"""

    def __init__(self):
        self._documents: dict[str, dict] = {}

    def add(self, ids, documents, embeddings, metadatas=None):
        for i, doc_id in enumerate(ids):
            self._documents[doc_id] = {
                "document": documents[i],
                "embedding": embeddings[i],
                "metadata": metadatas[i] if metadatas else {},
            }

    def query(self, query_embeddings, n_results=5, where=None):
        import numpy as np
        query = np.array(query_embeddings[0])
        results = []
        for doc_id, doc in self._documents.items():
            if where and not self._match_metadata(doc["metadata"], where):
                continue
            emb = np.array(doc["embedding"])
            similarity = np.dot(query, emb) / (np.linalg.norm(query) * np.linalg.norm(emb) + 1e-10)
            results.append((similarity, doc_id, doc))
        results.sort(key=lambda x: x[0], reverse=True)
        top = results[:n_results]
        return {
            "ids": [[r[1] for r in top]],
            "documents": [[r[2]["document"] for r in top]],
            "metadatas": [[r[2]["metadata"] for r in top]],
            "distances": [[1 - r[0] for r in top]],
        }

    def delete(self, ids):
        for doc_id in ids:
            self._documents.pop(doc_id, None)

    def count(self):
        return len(self._documents)

    def _match_metadata(self, metadata, where):
        for key, value in where.items():
            if metadata.get(key) != value:
                return False
        return True
