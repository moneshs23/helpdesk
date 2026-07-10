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
from backend.utils.logging import logger

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or",
    "in", "on", "for", "with", "how", "what", "when", "where", "why", "do",
    "does", "can", "i", "my", "you", "your", "it", "this", "that", "please",
    "me", "us", "we", "provide", "give", "tell", "kindly", "would", "could",
}


_CJK_RUN_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿｡-ﾟ]+")


def _cjk_bigrams(text: str, limit: int = 16) -> list[str]:
    """Cheap CJK 'tokenization' as character bigrams over each script run.

    Japanese has no whitespace word boundaries, and this codebase has no
    morphological analyzer — bigram overlap is a standard lightweight
    fallback for exact-ish substring matching against Japanese ticket text
    (e.g. half-width katakana "ｼｰﾄﾍﾞﾙﾄ") that a translated-to-English query
    alone could never match.
    """
    bigrams: list[str] = []
    for run in _CJK_RUN_RE.findall(text):
        bigrams.extend(run[i : i + 2] for i in range(len(run) - 1))
    return bigrams[:limit]


def _identifier_like(token: str) -> bool:
    """Part numbers / VINs: alphanumeric tokens containing a digit. Threshold
    of 6 covers short fleet codes used as VINs (e.g. '505038') as well as
    full 17-char VINs and part numbers like '75725b'."""
    return len(token) >= 6 and any(ch.isdigit() for ch in token)


def _prioritize_identifier_chunks(
    chunks: list[RetrievedChunk],
    identifiers: list[str],
    top_k: int,
    max_same_id: int = 7,
) -> list[RetrievedChunk]:
    """When the query quotes an identifier (VIN/part number), keep EVERY
    ranked chunk containing it — one vehicle can have several tickets sharing
    a VIN, and slicing to top_k before the LLM sees them would arbitrarily
    drop the ticket whose question actually matches. Non-matching chunks fill
    any remaining top_k budget after the identifier group."""
    if not identifiers:
        return chunks[:top_k]
    matching = [
        c for c in chunks
        if any(i in c.text.lower() for i in identifiers)
    ][:max_same_id]
    if not matching:
        return chunks[:top_k]
    matched_ids = {c.id for c in matching}
    rest = [c for c in chunks if c.id not in matched_ids]
    return matching + rest[: max(0, top_k - len(matching))]


def _keywords(text: str) -> list[str]:
    """Extract exact-match tokens (part numbers, VINs, codes) a query cares
    about — these often matter more than semantic similarity, since embedding
    models don't reliably distinguish one alphanumeric code from another."""
    all_tokens = [
        t for t in re.findall(r"[A-Za-z0-9]{2,}", text.lower())
        if t not in _STOPWORDS
    ]
    tokens = all_tokens[:12]
    # Identifiers (VIN, part number) must survive the cap even when they
    # appear at the end of a long query — users often append the VIN last.
    tokens += [t for t in all_tokens[12:] if _identifier_like(t)]
    tokens += _cjk_bigrams(text)
    return tokens


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
            "_kw_hit": False,
        }
    for h, nk in zip(keyword, kw_norm):
        if h["id"] in combined:
            combined[h["id"]]["_rank"] += (1 - alpha) * nk
            combined[h["id"]]["_kw_hit"] = True
        else:
            combined[h["id"]] = {
                "id": h["id"],
                "payload": h["payload"],
                "score": 0.0,  # keyword-only hit, no semantic cosine
                "_rank": (1 - alpha) * nk,
                "_kw_hit": True,
            }

    # Exact keyword matches (e.g. a part number or VIN) are a stronger, more
    # deterministic relevance signal than cosine similarity for this domain,
    # and a tiny candidate pool makes normalized-score ties common — so a
    # confirmed keyword hit always outranks a same-score keyword-less one
    # instead of losing on dict/insertion-order tie-breaking.
    return sorted(
        combined.values(), key=lambda x: (x["_kw_hit"], x["_rank"]), reverse=True
    )


async def retrieve_documents(
    query: str,
    *,
    top_k: int | None = None,
    product: str | None = None,
    doc_type: str | None = None,
    mode: str = "hybrid",
    vector: list[float] | None = None,
    extra_keyword_text: str | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or settings.top_k_docs
    store = get_vector_store()
    embedder = get_embedder()
    # A wider merge pool than top_k (esp. when top_k=1) so min-max
    # normalization has enough spread to be meaningful instead of collapsing
    # a single candidate to a false 1.0 and creating spurious rank ties.
    fan_out = max(top_k * 2, 8)

    semantic: list[dict] = []
    if mode in ("hybrid", "semantic"):
        vector = vector or await embedder.embed_query(query)
        semantic = await store.search_documents(
            vector, top_k=fan_out, product=product, doc_type=doc_type
        )

    keyword: list[dict] = []
    if mode in ("hybrid", "keyword"):
        # `query` is the (possibly translated-to-English) working query; when
        # the customer originally wrote in another script, that translation
        # has already lost the exact original wording. `extra_keyword_text`
        # lets the caller pass the pre-translation text so its native-script
        # tokens (e.g. Japanese) still get a chance at an exact-match hit
        # against ticket content stored in that same script.
        kw_terms = _keywords(query)
        if extra_keyword_text:
            kw_terms += _keywords(extra_keyword_text)
        keyword = await store.keyword_search(
            kw_terms, limit=fan_out, product=product, doc_type=doc_type
        )

    if mode == "semantic":
        merged = semantic
    elif mode == "keyword":
        merged = keyword
    else:
        merged = _merge_hybrid(semantic, keyword)

    chunks = [_to_chunk(h) for h in merged]
    chunks = _dedupe(chunks)
    # A keyword-only hit (no semantic cosine) still clears the gate as long as
    # it actually matched query tokens — only drop it if it scored 0 there too.
    chunks = [
        c for c in chunks if c.score >= settings.min_score_threshold or c.score == 0.0
    ]
    identifiers = [t for t in _keywords(query) if _identifier_like(t)]
    if extra_keyword_text:
        identifiers += [
            t for t in _keywords(extra_keyword_text) if _identifier_like(t)
        ]
    chunks = _prioritize_identifier_chunks(chunks, identifiers, top_k)

    # ── Graph expansion (optional, when Neo4j is enabled) ──
    if settings.neo4j_enabled:
        chunks = await _graph_expand(query, chunks, top_k)

    return chunks


async def _graph_expand(
    query: str, chunks: list[RetrievedChunk], top_k: int
) -> list[RetrievedChunk]:
    """Enhance retrieval results with graph-related chunks from Neo4j."""
    try:
        from backend.graph import get_graph_store

        graph = get_graph_store()
        if graph is None:
            return chunks

        # Get chunk IDs already retrieved by vector search
        existing_ids = {c.id for c in chunks}

        # Ask the graph for related chunks via entity/relationship traversal
        related = await graph.get_related_chunks(
            [c.id for c in chunks], depth=1
        )

        if not related:
            return chunks

        # Boost existing chunks that also appear in graph results
        graph_chunk_ids = {r["chunk_id"] for r in related}
        weight = settings.graph_retrieval_weight
        for chunk in chunks:
            if chunk.id in graph_chunk_ids:
                chunk.score = min(1.0, chunk.score + weight * 0.2)

        logger.debug(
            f"Graph expansion: {len(related)} related chunks found, "
            f"{len(graph_chunk_ids & existing_ids)} overlapping"
        )

        return chunks[:top_k]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Graph expansion failed, using vector-only: {exc}")
        return chunks


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


async def retrieve_conversations(
    query: str,
    *,
    top_k: int | None = None,
    product: str | None = None,
    vector: list[float] | None = None,
) -> list[SimilarConversation]:
    top_k = top_k or settings.top_k_chats
    store = get_vector_store()
    embedder = get_embedder()
    vector = vector or await embedder.embed_query(query)
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
