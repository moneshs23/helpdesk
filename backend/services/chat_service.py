"""Chat service: orchestrates the RAG pipeline and persists conversation memory."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ConversationORM
from backend.embeddings import get_embedder
from backend.models.enums import ConversationStatus
from backend.models.schemas import ChatRequest, ChatResponse
from backend.qdrant import get_vector_store
from backend.rag.pipeline import run_chat
from backend.utils.logging import logger


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.store = get_vector_store()
        self.embedder = get_embedder()

    async def process(self, request: ChatRequest) -> ChatResponse:
        response = await run_chat(request)
        if request.persist:
            await self._persist(request, response)
        return response

    async def _persist(self, request: ChatRequest, response: ChatResponse) -> None:
        best = response.suggestions[0] if response.suggestions else None
        final_reply = best.answer_en if best else ""
        confidence = best.confidence if best else 0.0

        record = ConversationORM(
            conversation_id=response.conversation_id,
            customer_id=request.customer_id or "",
            agent_name=request.agent_name or "",
            product=request.product or "",
            question=response.original_message,
            detected_language=response.detected_language.value,
            translated_query=response.translated_query,
            final_reply=final_reply,
            confidence=confidence,
            status=(
                ConversationStatus.ANSWERED.value
                if response.grounded
                else ConversationStatus.PENDING.value
            ),
            response_time_ms=response.response_time_ms,
            created_at=response.created_at,
        )
        self.session.add(record)
        await self.session.flush()

        # Store embedding for future semantic memory search.
        try:
            vector = await self.embedder.embed_query(response.translated_query)
            await self.store.upsert_conversation(
                vector,
                {
                    "conversation_id": response.conversation_id,
                    "question": response.original_message,
                    "translated_query": response.translated_query,
                    "answer": final_reply,
                    "agent_name": request.agent_name or "Unknown",
                    "product": request.product or "",
                    "created_at": (response.created_at or datetime.now(timezone.utc)).isoformat(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to index conversation embedding: {exc}")
