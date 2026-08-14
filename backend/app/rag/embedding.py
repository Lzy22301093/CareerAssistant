"""Embedding Service — 文本向量化服务。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingService:
    """文本 Embedding 服务，支持多种后端。"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        """延迟加载模型。"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                logger.info(f"Loaded embedding model: {self._model_name}")
            except ImportError:
                logger.warning("sentence_transformers not available, using dummy embeddings")
                self._model = "dummy"
        return self._model

    def embed(self, text: str) -> list[float]:
        """将文本转换为向量。"""
        model = self._get_model()
        if model == "dummy":
            # 返回固定维度的随机向量（用于测试）
            import hashlib
            hash_val = hashlib.md5(text.encode()).hexdigest()
            return [float(int(hash_val[i:i+2], 16)) / 255.0 for i in range(0, 32, 2)]
        return model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转换为向量。"""
        model = self._get_model()
        if model == "dummy":
            return [self.embed(t) for t in texts]
        return model.encode(texts).tolist()

    @property
    def dimension(self) -> int:
        """返回向量维度。"""
        model = self._get_model()
        if model == "dummy":
            return 16
        return model.get_sentence_embedding_dimension()
