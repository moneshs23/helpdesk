"""End-to-end RAG chat pipeline.

detect language → translate → rewrite → retrieve (docs + chats) → merge context
→ Gemma Top-3 grounded generation → translate answers back.
"""
from __future__ import annotations

import time
import uuid
import asyncio
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
from backend.embeddings import get_embedder
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

    # 4) Retrieve documents + previous conversations. Reuse one embedding and
    # run both vector searches together to avoid duplicate Ollama calls.
    vector = await get_embedder().embed_query(rewritten)
    chunks, similar = await asyncio.gather(
        retrieve_documents(
            rewritten,
            top_k=request.top_k_docs or settings.top_k_docs,
            product=request.product,
            mode="hybrid",
            vector=vector,
            # Translation loses exact original wording — pass the
            # pre-translation text too so native-script (e.g. Japanese)
            # keyword matching can still hit ticket content in that script.
            extra_keyword_text=safe_message if detected != Language.EN else None,
        ),
        retrieve_conversations(
            rewritten,
            top_k=request.top_k_chats or settings.top_k_chats,
            product=request.product,
            vector=vector,
        ),
    )

    # 5) Relevance gate (enforce the no-hallucination policy up front).
    # retrieve_documents() already filters for relevance internally (semantic
    # score >= threshold, OR a confirmed keyword match reported as score=0.0
    # by design) — so an empty result here is the actual "nothing relevant"
    # signal. Re-checking score against the threshold here would wrongly
    # reject legitimate keyword-only matches (e.g. an exact part number/VIN
    # with no strong semantic overlap).
    reply_lang = _resolve_reply_language(request.reply_language, detected)
    ticket_chunks = [c for c in chunks if "Closed:" in c.text and "Opened:" in c.text]
    if not chunks:
        logger.info("No chunk cleared retrieval relevance; returning no-info.")
        suggestions, grounded = _no_info_suggestions(), False
    elif ticket_chunks:
        # Ticket data: the answer already exists verbatim in the Closed: text.
        # The LLM only SELECTS the matching ticket — the answer itself is
        # copied from the document, never composed, so it can't drift from
        # what the original agent actually replied.
        suggestions, grounded = await _extractive_suggestions(
            translated_query,
            ticket_chunks,
            reply_lang,
            original_query=safe_message if detected != Language.EN else None,
        )
    else:
        # Conversation memory (`similar`) is still returned to the agent below
        # for reference, but is left out of the generation prompt itself — on
        # CPU-only inference, every extra token of context costs real time,
        # and the single retrieved chunk is normally the complete answer.
        context, source_map = build_context(chunks, [])
        suggestions, grounded = await _generate_suggestions(
            translated_query, context, source_map
        )

    # 6) Translate the top answer back if the reply language is Japanese.
    # Extractive suggestions may already carry a verbatim-Japanese answer_ja —
    # keep it untouched. Only rank 1 is auto-translated: the customer receives
    # one reply, and translating the alternates would double or triple the
    # LLM round-trips for text the agent usually never sends (the /translate
    # endpoint covers the rare case where an alternate is chosen).
    if reply_lang == Language.JA and suggestions:
        top = suggestions[0]
        if not top.answer_ja:
            top.answer_ja, _ = await translator.translate(
                top.answer_en, Language.EN, Language.JA
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


# Tiny selection task: the model outputs ~10 tokens (a source number), so the
# whole cost is prompt evaluation — and the verbatim Closed: text can never be
# misquoted the way composed answers were.
# Forced choice on purpose: retrieval already gated relevance, and offering a
# "none match" escape (source 0) made the small model take it even for
# obvious matches, collapsing good retrievals into no-answer responses.
_SELECT_SYSTEM = (
    "You match a customer question to numbered support-ticket questions. "
    "Tickets may share a VIN — same vehicle, different subjects. Choose the "
    "single ticket about the same subject as the customer's question. "
    'Reply with VALID JSON only: {"source": N}.'
)


def _extract_closed(text: str) -> str:
    """Return the verbatim Closed: segment of a ticket chunk."""
    idx = text.rfind("Closed:")
    if idx == -1:
        return ""
    return text[idx + len("Closed:") :].strip()


def _opened_excerpt(text: str, limit: int = 240) -> str:
    """VIN + Opened: question of a ticket chunk, without its Closed: answer.

    The selection step only needs to compare questions — feeding the answers
    too roughly doubles the prompt, and prompt evaluation is the dominant
    cost of the whole request on CPU-only inference.
    """
    end = text.rfind("Closed:")
    head = text[: end if end != -1 else len(text)].strip(" ;\n")
    return head[:limit]


async def _extractive_suggestions(
    query: str,
    chunks: list,
    reply_lang: Language,
    original_query: str | None = None,
) -> tuple[list[Suggestion], bool]:
    """Answer by copying the matched ticket's Closed: text verbatim.

    The chosen source's Closed: text IS the answer. If it's Japanese, the
    customer-facing answer_ja is that original text untouched (no round-trip
    translation to corrupt part numbers) and answer_en is a translation for
    the agent console; answer_ja is only populated when the reply language
    resolves to Japanese.
    """
    translator = get_translator()
    if len(chunks) == 1:
        # Nothing to disambiguate — skip the selection LLM call entirely.
        chosen = chunks[0]
    else:
        sources = "\n".join(
            f"[{i}] {_opened_excerpt(c.text)}" for i, c in enumerate(chunks, 1)
        )
        # Include the customer's original-language wording: a Japanese
        # question often IS (near-)verbatim some ticket's Opened: text,
        # making selection an exact string match instead of a cross-language
        # paraphrase judgement.
        question = f"CUSTOMER QUESTION: {query}"
        if original_query:
            question += f"\nCUSTOMER QUESTION (original wording): {original_query}"
        prompt = f"TICKET QUESTIONS:\n{sources}\n\n{question}\n\nJSON:"
        data = await get_llm().generate_json(
            prompt, system=_SELECT_SYSTEM, temperature=0.0, num_predict=16
        )
        try:
            n = int(data.get("source", 1))
        except (TypeError, ValueError):
            n = 1
        chosen = chunks[n - 1] if 1 <= n <= len(chunks) else chunks[0]

    ordered = [chosen] + [c for c in chunks if c.id != chosen.id]
    suggestions: list[Suggestion] = []
    for i, c in enumerate(ordered[:3], start=1):
        closed = _extract_closed(c.text)
        if not closed:
            continue
        answer_ja = None
        answer_en = closed
        if detect_language(closed) == Language.JA:
            if reply_lang == Language.JA:
                answer_ja = closed  # verbatim original — never re-translated
            if i == 1:
                # Only the chosen answer is translated for the console —
                # translating alternates the agent rarely opens would add an
                # LLM round-trip (~15s) apiece. Alternates keep the original
                # text; the /translate endpoint covers them on demand.
                answer_en, _ = await translator.translate(
                    closed, Language.JA, Language.EN
                )
        suggestions.append(
            Suggestion(
                rank=len(suggestions) + 1,
                answer_en=answer_en,
                answer_ja=answer_ja,
                confidence=0.95 if i == 1 else 0.5,
                reasoning="",
                referenced_documents=[c.metadata.filename],
                referenced_pages=[c.metadata.page],
            )
        )
    if not suggestions:
        return _no_info_suggestions(), False
    return suggestions, True


async def _generate_suggestions(
    query: str, context: str, source_map: dict
) -> tuple[list[Suggestion], bool]:
    if not source_map:
        return _no_info_suggestions(), False

    prompt = build_generation_prompt(query, context)
    llm = get_llm()
    # temperature=0.0 so the same query always yields the same answer —
    # sampling at the default temperature made grounded answers flip between
    # correct and wrong across identical runs.
    data = await llm.generate_json(
        prompt,
        system=SYSTEM_PROMPT,
        temperature=0.0,
        num_predict=settings.llm_suggestion_num_predict,
    )

    raw_suggestions = data.get("suggestions") or []
    if not raw_suggestions:
        # One retry: models occasionally emit malformed JSON on large contexts.
        logger.info("Empty suggestions; retrying generation once.")
        data = await llm.generate_json(
            prompt,
            system=SYSTEM_PROMPT,
            temperature=0.0,
            num_predict=settings.llm_suggestion_num_predict,
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
