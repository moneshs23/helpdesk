"""End-to-end RAG chat pipeline.

detect language → translate → rewrite → retrieve (docs + chats) → merge context
→ Gemma Top-3 grounded generation → translate answers back.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from backend.config import settings
from backend.llm import get_llm
from backend.models.enums import Language
from backend.models.schemas import ChatRequest, ChatResponse, Suggestion
from backend.rag.prompt import (
    NO_INFO_MESSAGE,
    SYSTEM_PROMPT,
    build_context,
    build_generation_prompt,
)
from backend.rag.retriever import retrieve_conversations, retrieve_documents
from backend.translation import detect_language, get_translator
from backend.utils.logging import logger
from backend.utils.security import neutralize_injection


async def _rewrite_query(query: str) -> str:
    """Lightweight query rewrite to improve retrieval (keeps it fast)."""
    try:
        system = (
            "Rewrite the user's support question into a concise, keyword-rich search "
            "query for document retrieval. Output only the rewritten query."
        )
        rewritten = await get_llm().generate(query, system=system, temperature=0.0, num_predict=40)
        return rewritten.strip() or query
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Query rewrite failed: {exc}")
        return query


def _resolve_reply_language(
    reply_language: Language, detected: Language
) -> Language:
    if reply_language in (Language.AUTO, Language.UNKNOWN):
        return detected
    return reply_language


async def run_chat(request: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    translator = get_translator()
    llm = get_llm()

    raw_message = request.message.strip()
    safe_message = neutralize_injection(raw_message)

    # 1) Language detection
    detected = (
        detect_language(safe_message)
        if request.language == Language.AUTO
        else request.language
    )

    # 2) Translate to English (internal working language)
    if detected == Language.JA:
        translated_query, _ = await translator.translate(
            safe_message, Language.JA, Language.EN
        )
    else:
        translated_query = safe_message

    # 3) Rewrite for retrieval (optional; off by default for lower latency)
    rewritten = (
        await _rewrite_query(translated_query)
        if settings.enable_query_rewrite
        else translated_query
    )

    # 4) Retrieve documents + previous conversations
    chunks = await retrieve_documents(
        rewritten,
        top_k=request.top_k_docs or settings.top_k_docs,
        product=request.product,
        mode="hybrid",
    )
    similar = await retrieve_conversations(
        rewritten,
        top_k=request.top_k_chats or settings.top_k_chats,
        product=request.product,
    )

    # 5) Relevance gate (enforce the no-hallucination policy up front).
    has_relevant = any(c.score >= settings.min_score_threshold for c in chunks)
    if not has_relevant:
        logger.info("No chunk cleared the relevance threshold; returning no-info.")
        suggestions, grounded = _no_info_suggestions(), False
    else:
        context, source_map = build_context(chunks, similar)
        suggestions, grounded = await _generate_suggestions(
            translated_query, context, source_map
        )

    # 6) Translate answers back if the reply language is Japanese
    reply_lang = _resolve_reply_language(request.reply_language, detected)
    if reply_lang == Language.JA:
        for s in suggestions:
            s.answer_ja, _ = await translator.translate(
                s.answer_en, Language.EN, Language.JA
            )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    conversation_id = request.conversation_id or str(uuid.uuid4())

    return ChatResponse(
        conversation_id=conversation_id,
        detected_language=detected,
        original_message=raw_message,
        translated_query=translated_query,
        rewritten_query=rewritten,
        suggestions=suggestions,
        retrieved_documents=chunks,
        similar_conversations=similar,
        grounded=grounded,
        response_time_ms=elapsed_ms,
        created_at=datetime.now(timezone.utc),
    )


async def _generate_suggestions(
    query: str, context: str, source_map: dict
) -> tuple[list[Suggestion], bool]:
    if not source_map:
        return _no_info_suggestions(), False

    prompt = build_generation_prompt(query, context)
    llm = get_llm()
    data = await llm.generate_json(prompt, system=SYSTEM_PROMPT, num_predict=1200)

    raw_suggestions = data.get("suggestions") or []
    if not raw_suggestions:
        # One retry: models occasionally emit malformed JSON on large contexts.
        logger.info("Empty suggestions; retrying generation once.")
        data = await llm.generate_json(
            prompt, system=SYSTEM_PROMPT, temperature=0.0, num_predict=1200
        )
        raw_suggestions = data.get("suggestions") or []

    if not raw_suggestions:
        return _no_info_suggestions(), False

    suggestions: list[Suggestion] = []
    any_cited = False
    for i, item in enumerate(raw_suggestions[:3], start=1):
        answer = (item.get("answer") or "").strip()
        if not answer or answer == NO_INFO_MESSAGE:
            continue
        sources = item.get("sources") or []
        docs, pages = _resolve_sources(sources, source_map)
        if docs:
            any_cited = True
        confidence = float(item.get("confidence", 0.0) or 0.0)
        if not docs:
            confidence = min(confidence, 0.2)
        suggestions.append(
            Suggestion(
                rank=i,
                answer_en=answer,
                confidence=max(0.0, min(1.0, confidence)),
                reasoning=(item.get("reasoning") or "").strip(),
                referenced_documents=docs,
                referenced_pages=pages,
            )
        )

    if not suggestions:
        return _no_info_suggestions(), False

    # Grounded when the model self-reports it OR any suggestion cites a source.
    grounded = bool(data.get("grounded", False)) or any_cited
    for idx, s in enumerate(suggestions, start=1):
        s.rank = idx
    return suggestions, grounded


def _resolve_sources(
    sources: list, source_map: dict
) -> tuple[list[str], list[int]]:
    docs: list[str] = []
    pages: list[int] = []
    for s in sources:
        try:
            n = int(s)
        except (ValueError, TypeError):
            continue
        chunk = source_map.get(n)
        if chunk:
            fname = chunk.metadata.filename
            if fname and fname not in docs:
                docs.append(fname)
            if chunk.metadata.page and chunk.metadata.page not in pages:
                pages.append(chunk.metadata.page)
    return docs, pages


def _no_info_suggestions() -> list[Suggestion]:
    return [
        Suggestion(
            rank=1,
            answer_en=NO_INFO_MESSAGE,
            confidence=0.0,
            reasoning="No relevant content was found in the uploaded documents.",
            referenced_documents=[],
            referenced_pages=[],
        )
    ]
