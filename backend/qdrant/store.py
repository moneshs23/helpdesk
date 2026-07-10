"""Qdrant vector store wrapper (local embedded mode).

Manages two collections:
- ``documents``     : chunks from uploaded company documents.
- ``conversations`` : embeddings of past customer questions for memory search.

The local (path-based) Qdrant client is synchronous, so blocking calls are
off-loaded to a worker thread to keep the FastAPI event loop responsive.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import anyio
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from backend.config import settings
from backend.utils.logging import logger


def _new_id() -> str:
    return str(uuid.uuid4())


class VectorStore:
    def __init__(self) -> None:
        if settings.qdrant_mode == "server":
            self._client = QdrantClient(
                host=settings.qdrant_host, port=settings.qdrant_port
            )
        else:
            self._client = QdrantClient(path=str(settings.qdrant_local_path))
        self.docs = settings.qdrant_docs_collection
        self.chats = settings.qdrant_chats_collection
        self.dim = settings.embedding_dim
        self._ensure_collections()

    # ---------------- setup ----------------
    def _ensure_collection(self, name: str) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if name in existing:
            return
        self._client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(
                size=self.dim, distance=qm.Distance.COSINE
            ),
            hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=100),
            optimizers_config=qm.OptimizersConfigDiff(default_segment_number=2),
        )
        logger.info(f"Created Qdrant collection: {name}")

    def _ensure_collections(self) -> None:
        self._ensure_collection(self.docs)
        self._ensure_collection(self.chats)
        # Payload indexes speed up filtered search.
        for field in ("document_id", "filename", "product", "doc_type"):
            self._safe_index(self.docs, field, qm.PayloadSchemaType.KEYWORD)
        for field in ("conversation_id", "product", "agent_name"):
            self._safe_index(self.chats, field, qm.PayloadSchemaType.KEYWORD)

    def _safe_index(self, collection: str, field: str, schema: Any) -> None:
        try:
            self._client.create_payload_index(collection, field, field_schema=schema)
        except Exception:  # noqa: BLE001 - index may already exist
            pass

    # ---------------- documents ----------------
    def _upsert_documents_sync(
        self, vectors: list[list[float]], payloads: list[dict], texts: list[str]
    ) -> list[str]:
        points = []
        ids: list[str] = []
        for vec, payload, text in zip(vectors, payloads, texts):
            pid = _new_id()
            ids.append(pid)
            points.append(
                qm.PointStruct(id=pid, vector=vec, payload={**payload, "text": text})
            )
        self._client.upsert(collection_name=self.docs, points=points)
        return ids

    async def upsert_documents(
        self, vectors: list[list[float]], payloads: list[dict], texts: list[str]
    ) -> list[str]:
        return await anyio.to_thread.run_sync(
            self._upsert_documents_sync, vectors, payloads, texts
        )

    def _search_documents_sync(
        self, vector: list[float], top_k: int, flt: Optional[qm.Filter]
    ) -> list[dict]:
        res = self._client.search(
            collection_name=self.docs,
            query_vector=vector,
            limit=top_k,
            query_filter=flt,
            with_payload=True,
        )
        return [{"id": str(p.id), "score": p.score, "payload": p.payload} for p in res]

    async def search_documents(
        self,
        vector: list[float],
        top_k: int = 6,
        product: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> list[dict]:
        conditions = []
        if product:
            conditions.append(
                qm.FieldCondition(key="product", match=qm.MatchValue(value=product))
            )
        if doc_type:
            conditions.append(
                qm.FieldCondition(key="doc_type", match=qm.MatchValue(value=doc_type))
            )
        flt = qm.Filter(must=conditions) if conditions else None
        return await anyio.to_thread.run_sync(
            self._search_documents_sync, vector, top_k, flt
        )

    def _keyword_search_sync(
        self, keywords: list[str], limit: int, flt: Optional[qm.Filter]
    ) -> list[dict]:
        """Score chunks by whole-word keyword hit density in their text.

        A full scan (not a Qdrant text index) — simplest correct option, and
        genuinely fast at this collection's scale (hundreds to low thousands
        of chunks), which is exactly what row-oriented ticket documents produce.

        Whole-word matching (not substring) avoids false hits like "me"
        matching inside "odometer"/"speedometer". Scoring by hits-per-character
        rather than a raw count also matters: without it, a long prose chunk
        that happens to contain a few generic words (e.g. "part", "number")
        many times over outscores a short, precise ticket row that mentions
        the same words only once — exactly backwards for this domain.

        CJK keywords (Japanese character bigrams — see retriever._cjk_bigrams)
        are matched as plain substrings instead: Python's `\\b` never asserts
        a boundary between two adjacent CJK characters (both count as `\\w`),
        so `\\b`-anchoring would silently never match inside continuous
        Japanese text.
        """
        if not keywords:
            return []
        _cjk = re.compile(r"[぀-ヿ㐀-䶿一-鿿｡-ﾟ]")
        # Each pattern carries the keyword's length as its match weight: a hit
        # on a long identifier (17-char VIN, 8-char part number) is a far
        # stronger relevance signal than a hit on a generic 4-char word, and
        # a query that quotes a VIN must rank that vehicle's own ticket first.
        # CJK bigrams get double weight — 2 visual characters carry roughly a
        # word's worth of meaning, and length-weighting alone would let an
        # English paraphrase outrank an exact Japanese-script match.
        weighted = [
            (
                (re.compile(re.escape(kw)), len(kw) * 2)
                if _cjk.search(kw)
                else (re.compile(rf"\b{re.escape(kw)}\b"), len(kw))
            )
            for kw in keywords
        ]
        scored: list[tuple[float, dict]] = []
        next_page = None
        while True:
            points, next_page = self._client.scroll(
                collection_name=self.docs,
                scroll_filter=flt,
                limit=256,
                offset=next_page,
                with_payload=True,
            )
            for p in points:
                text = str((p.payload or {}).get("text", "")).lower()
                if not text:
                    continue
                hits = sum(len(pat.findall(text)) * w for pat, w in weighted)
                if hits > 0:
                    density = hits / len(text)
                    scored.append(
                        (density, {"id": str(p.id), "score": float(hits), "payload": p.payload})
                    )
            if next_page is None:
                break
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    async def keyword_search(
        self,
        keywords: list[str],
        limit: int = 12,
        product: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> list[dict]:
        conditions = []
        if product:
            conditions.append(
                qm.FieldCondition(key="product", match=qm.MatchValue(value=product))
            )
        if doc_type:
            conditions.append(
                qm.FieldCondition(key="doc_type", match=qm.MatchValue(value=doc_type))
            )
        flt = qm.Filter(must=conditions) if conditions else None
        return await anyio.to_thread.run_sync(
            self._keyword_search_sync, keywords, limit, flt
        )

    def _delete_document_sync(self, document_id: str) -> None:
        self._client.delete(
            collection_name=self.docs,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id",
                            match=qm.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    async def delete_document(self, document_id: str) -> None:
        await anyio.to_thread.run_sync(self._delete_document_sync, document_id)

    # ---------------- conversations ----------------
    def _upsert_conversation_sync(self, vector: list[float], payload: dict) -> str:
        pid = _new_id()
        self._client.upsert(
            collection_name=self.chats,
            points=[qm.PointStruct(id=pid, vector=vector, payload=payload)],
        )
        return pid

    async def upsert_conversation(self, vector: list[float], payload: dict) -> str:
        payload = {**payload, "indexed_at": datetime.now(timezone.utc).isoformat()}
        return await anyio.to_thread.run_sync(
            self._upsert_conversation_sync, vector, payload
        )

    def _search_conversations_sync(
        self, vector: list[float], top_k: int, flt: Optional[qm.Filter]
    ) -> list[dict]:
        res = self._client.search(
            collection_name=self.chats,
            query_vector=vector,
            limit=top_k,
            query_filter=flt,
            with_payload=True,
        )
        return [{"id": str(p.id), "score": p.score, "payload": p.payload} for p in res]

    async def search_conversations(
        self, vector: list[float], top_k: int = 4, product: Optional[str] = None
    ) -> list[dict]:
        conditions = []
        if product:
            conditions.append(
                qm.FieldCondition(key="product", match=qm.MatchValue(value=product))
            )
        flt = qm.Filter(must=conditions) if conditions else None
        return await anyio.to_thread.run_sync(
            self._search_conversations_sync, vector, top_k, flt
        )

    # ---------------- stats ----------------
    def _count_sync(self, collection: str) -> int:
        try:
            return self._client.count(collection, exact=True).count
        except Exception:  # noqa: BLE001
            return 0

    async def count_documents(self) -> int:
        return await anyio.to_thread.run_sync(self._count_sync, self.docs)

    async def count_conversations(self) -> int:
        return await anyio.to_thread.run_sync(self._count_sync, self.chats)


_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
