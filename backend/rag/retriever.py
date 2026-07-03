"""Retrieval: hybrid (semantic + keyword) document search and conversation memory."""
from __future__ import annotations

import re
from datetime import datetime

from backend.config import settings
from backend.embeddings import get_embedder
from backend.models.enums import DocumentType
from backend.models.schemas import (
    ChunkMetadata,
    RetrievedChunk,
    SimilarConversation,
)
from backend.qdrant import get_vector_store

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or",
    "in", "on", "for", "with", "how", "what", "when", "where", "why", "do",
    "does", "can", "i", "my", "you", "your", "it", "this", "that", "please",
}


def _keywords(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9]{2,}", text.lower())
    return [t for t in tokens if t not in _STOPWORDS][:12]


def _to_chunk(hit: dict) -> RetrievedChunk:
    p = hit.get("payload", {}) or {}
    upload_date = p.get("upload_date")
    parsed_date: datetime | None = None
    if upload_date:
        try:
            parsed_date = datetime.fromisoformat(upload_date)
        except ValueError:
            parsed_date = None
    meta = ChunkMetadata(
        document_id=p.get("document_id", ""),
        filename=p.get("filename", ""),
        title=p.get("title", "") or p.get("filename", ""),
        doc_type=DocumentType.from_extension(p.get("doc_type", "")),
        page=int(p.get("page", 0) or 0),
        section=p.get("section", "") or "",
        upload_date=parsed_date,
        chunk_index=int(p.get("chunk_index", 0) or 0),
    )
    return RetrievedChunk(
        id=hit.get("id", ""),
        text=p.get("text", ""),
        score=float(hit.get("score", 0.0)),
        metadata=meta,
    )


def _normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


async def retrieve_documents(
    query: str,
    *,
    top_k: int | None = None,
    product: str | None = None,
    doc_type: str | None = None,
    mode: str = "hybrid",
) -> list[RetrievedChunk]:
    top_k = top_k or settings.top_k_docs
    store = get_vector_store()
    embedder = get_embedder()

    semantic: list[dict] = []
    if mode in ("hybrid", "semantic"):
        vector = await embedder.embed_query(query)
        semantic = await store.search_documents(
            vector, top_k=top_k * 2, product=product, doc_type=doc_type
        )

    keyword: list[dict] = []
    if mode in ("hybrid", "keyword"):
        keyword = await store.keyword_search(_keywords(query), limit=top_k * 2)

    if mode == "semantic":
        merged = semantic
    elif mode == "keyword":
        merged = keyword
    else:
        merged = _merge_hybrid(semantic, keyword)

    chunks = [_to_chunk(h) for h in merged]
    chunks = _dedupe(chunks)
    if mode == "semantic":
        chunks = [c for c in chunks if c.score >= settings.min_score_threshold]
    return chunks[:top_k]


def _dedupe(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Drop near-identical chunks (same document + page + text)."""
    seen: set[str] = set()
    unique: list[RetrievedChunk] = []
    for c in chunks:
        key = f"{c.metadata.document_id}|{c.metadata.page}|{c.text.strip()[:120]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique


def _merge_hybrid(semantic: list[dict], keyword: list[dict]) -> list[dict]:
    """Rank by a weighted blend, but keep the true semantic cosine as the
    displayed/gating score so callers can reason about absolute relevance."""
    alpha = settings.hybrid_alpha
    sem_norm = _normalize([h["score"] for h in semantic])
    kw_norm = _normalize([h["score"] for h in keyword])

    combined: dict[str, dict] = {}
    for h, ns in zip(semantic, sem_norm):
        combined[h["id"]] = {
            "id": h["id"],
            "payload": h["payload"],
            "score": h["score"],  # true cosine
            "_rank": alpha * ns,
        }
    for h, nk in zip(keyword, kw_norm):
        if h["id"] in combined:
            combined[h["id"]]["_rank"] += (1 - alpha) * nk
        else:
            combined[h["id"]] = {
                "id": h["id"],
                "payload": h["payload"],
                "score": 0.0,  # keyword-only hit, no semantic cosine
                "_rank": (1 - alpha) * nk,
            }

    return sorted(combined.values(), key=lambda x: x["_rank"], reverse=True)


async def retrieve_conversations(
    query: str, *, top_k: int | None = None, product: str | None = None
) -> list[SimilarConversation]:
    top_k = top_k or settings.top_k_chats
    store = get_vector_store()
    embedder = get_embedder()
    vector = await embedder.embed_query(query)
    hits = await store.search_conversations(vector, top_k=top_k, product=product)

    results: list[SimilarConversation] = []
    for h in hits:
        p = h.get("payload", {}) or {}
        date_raw = p.get("created_at") or p.get("indexed_at")
        try:
            date = datetime.fromisoformat(date_raw) if date_raw else datetime.utcnow()
        except (ValueError, TypeError):
            date = datetime.utcnow()
        results.append(
            SimilarConversation(
                conversation_id=p.get("conversation_id", ""),
                question=p.get("question", ""),
                answer=p.get("answer", ""),
                agent_name=p.get("agent_name", "") or "Unknown",
                product=p.get("product") or None,
                date=date,
                similarity=float(h.get("score", 0.0)),
            )
        )
    return results
