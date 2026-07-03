"""Embedding generation via Ollama (`nomic-embed-text`).

Features:
- Async batch embedding (memory-friendly batches for M1/8GB).
- In-process TTL cache to avoid recomputing identical texts.
"""
from __future__ import annotations

import hashlib

from ollama import AsyncClient
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.utils.cache import TTLCache
from backend.utils.logging import logger

# nomic-embed-text works best with task prefixes.
_QUERY_PREFIX = "search_query: "
_DOC_PREFIX = "search_document: "


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class Embedder:
    def __init__(self) -> None:
        self._client = AsyncClient(host=settings.ollama_base_url)
        self._cache = TTLCache(maxsize=2048, ttl=6 * 3600)
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self.batch_size = settings.embedding_batch_size

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
    async def _embed_raw(self, inputs: list[str]) -> list[list[float]]:
        resp = await self._client.embed(model=self.model, input=inputs)
        return list(resp["embeddings"])

    async def _embed_prefixed(self, texts: list[str], prefix: str) -> list[list[float]]:
        results: list[list[float] | None] = [None] * len(texts)
        pending: list[int] = []
        pending_inputs: list[str] = []

        for i, text in enumerate(texts):
            cached = await self._cache.get(_key(prefix + text))
            if cached is not None:
                results[i] = cached
            else:
                pending.append(i)
                pending_inputs.append(prefix + text)

        for start in range(0, len(pending_inputs), self.batch_size):
            batch = pending_inputs[start : start + self.batch_size]
            idxs = pending[start : start + self.batch_size]
            vectors = await self._embed_raw(batch)
            for idx, prefixed, vec in zip(idxs, batch, vectors):
                results[idx] = vec
                await self._cache.set(_key(prefixed), vec)

        return [r if r is not None else [0.0] * self.dim for r in results]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed_prefixed(texts, _DOC_PREFIX)

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed_prefixed([text], _QUERY_PREFIX)
        return vectors[0]

    async def health(self) -> bool:
        try:
            await self.embed_query("healthcheck")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Embedder health check failed: {exc}")
            return False


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
