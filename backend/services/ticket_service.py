"""Two-sided ticket service.

Customer submits a question -> a PENDING ticket is created (question detected &
translated to English for the agent). The agent later attaches AI suggestions
(via /api/chat with persist=false) and sends a final reply, which is translated
back into the customer's language. The AI never replies to the customer directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ConversationORM
from backend.embeddings import get_embedder
from backend.models.enums import ConversationStatus, Language
from backend.models.schemas import (
    CustomerStatusResponse,
    TicketRecord,
)
from backend.qdrant import get_vector_store
from backend.translation import detect_language, get_translator
from backend.utils.logging import logger
from backend.utils.security import neutralize_injection


def _lang(value: str) -> Language:
    return Language(value) if value in Language._value2member_map_ else Language.EN


def _to_ticket(c: ConversationORM) -> TicketRecord:
    return TicketRecord(
        id=c.id,
        conversation_id=c.conversation_id,
        customer_id=c.customer_id or None,
        agent_name=c.agent_name or None,
        product=c.product or None,
        question=c.question,
        detected_language=_lang(c.detected_language),
        translated_query=c.translated_query,
        final_reply=c.final_reply,
        customer_reply=c.customer_reply or "",
        confidence=c.confidence,
        status=ConversationStatus(c.status)
        if c.status in ConversationStatus._value2member_map_
        else ConversationStatus.PENDING,
        response_time_ms=c.response_time_ms,
        created_at=c.created_at,
        answered_at=c.answered_at,
    )


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.translator = get_translator()

    async def create(
        self, *, message: str, customer_id: str | None = None, product: str | None = None
    ) -> TicketRecord:
        import uuid

        text = neutralize_injection(message.strip())
        lang = detect_language(text)
        if lang == Language.JA:
            translated, _ = await self.translator.translate(text, Language.JA, Language.EN)
        else:
            translated = text

        ticket = ConversationORM(
            conversation_id=uuid.uuid4().hex,
            customer_id=customer_id or "",
            agent_name="",
            product=product or "",
            question=text,
            detected_language=lang.value,
            translated_query=translated,
            final_reply="",
            customer_reply="",
            status=ConversationStatus.PENDING.value,
            source="customer",
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(ticket)
        await self.session.flush()
        logger.info(f"New customer ticket #{ticket.id} ({lang.value})")
        return _to_ticket(ticket)

    async def list(
        self, *, status: str | None = "pending", limit: int = 100
    ) -> tuple[list[TicketRecord], int]:
        stmt = select(ConversationORM).where(ConversationORM.source == "customer")
        if status and status != "all":
            stmt = stmt.where(ConversationORM.status == status)
        count = int(
            (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
            or 0
        )
        stmt = stmt.order_by(ConversationORM.created_at.desc()).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_ticket(c) for c in rows], count

    async def get(self, ticket_id: int) -> TicketRecord | None:
        c = await self.session.get(ConversationORM, ticket_id)
        return _to_ticket(c) if c else None

    async def customer_status(self, conversation_id: str) -> CustomerStatusResponse | None:
        stmt = (
            select(ConversationORM)
            .where(ConversationORM.conversation_id == conversation_id)
            .order_by(ConversationORM.created_at.desc())
            .limit(1)
        )
        c = (await self.session.execute(stmt)).scalars().first()
        if c is None:
            return None
        return CustomerStatusResponse(
            conversation_id=c.conversation_id,
            question=c.question,
            status=ConversationStatus(c.status)
            if c.status in ConversationStatus._value2member_map_
            else ConversationStatus.PENDING,
            reply=c.customer_reply or "",
            language=_lang(c.detected_language),
            agent_name=c.agent_name or None,
            answered_at=c.answered_at,
        )

    async def reply(
        self,
        ticket_id: int,
        *,
        reply: str,
        agent_name: str | None = None,
        confidence: float | None = None,
        resolved: bool = False,
    ) -> TicketRecord | None:
        c = await self.session.get(ConversationORM, ticket_id)
        if c is None:
            return None

        reply = reply.strip()
        c.final_reply = reply
        c.agent_edited_reply = reply
        if agent_name:
            c.agent_name = agent_name
        if confidence is not None:
            c.confidence = max(0.0, min(1.0, confidence))
        c.status = (
            ConversationStatus.RESOLVED.value
            if resolved
            else ConversationStatus.ANSWERED.value
        )
        c.answered_at = datetime.now(timezone.utc)

        # Translate the reply into the customer's language for display.
        cust_lang = _lang(c.detected_language)
        if cust_lang == Language.JA:
            translated, _ = await self.translator.translate(reply, Language.EN, Language.JA)
            c.customer_reply = translated
        else:
            c.customer_reply = reply

        await self.session.flush()

        # Index this Q&A into conversation memory for future semantic search.
        try:
            embedder = get_embedder()
            store = get_vector_store()
            vector = await embedder.embed_query(c.translated_query or c.question)
            await store.upsert_conversation(
                vector,
                {
                    "conversation_id": c.conversation_id,
                    "question": c.question,
                    "translated_query": c.translated_query,
                    "answer": reply,
                    "agent_name": c.agent_name or "Unknown",
                    "product": c.product or "",
                    "created_at": c.answered_at.isoformat(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to index ticket embedding: {exc}")

        logger.info(f"Ticket #{ticket_id} answered by {c.agent_name or 'agent'}")
        return _to_ticket(c)
