from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

from graphrag.config.enums import ModelType
from graphrag.language_model.factory import ModelFactory

from .config import load_settings


def local_embeddings_enabled() -> bool:
    return load_settings().graphrag_local_embeddings


@dataclass
class LocalEmbeddingModel:
    config: Any
    dimensions: int = 256

    async def aembed_batch(self, text_list: list[str], **kwargs: Any) -> list[list[float]]:
        return [self.embed(text, **kwargs) for text in text_list]

    async def aembed(self, text: str, **kwargs: Any) -> list[float]:
        return self.embed(text, **kwargs)

    def embed_batch(self, text_list: list[str], **kwargs: Any) -> list[list[float]]:
        return [self.embed(text, **kwargs) for text in text_list]

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        return _embed_text(text, self.dimensions)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\w+|[\u4e00-\u9fff]", text.lower(), flags=re.UNICODE)
    return tokens or [text.lower()]


def _embed_text(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def enable_local_embedding_fallback() -> bool:
    if not local_embeddings_enabled():
        return False

    def create_local_embedding_model(**kwargs: Any) -> LocalEmbeddingModel:
        return LocalEmbeddingModel(config=kwargs.get("config"))

    ModelFactory.register_embedding(ModelType.Embedding.value, create_local_embedding_model)
    return True
