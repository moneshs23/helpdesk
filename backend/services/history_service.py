"""Conversation history service: search, update, delete, export."""
from __future__ import annotations

import csv
import io
import json

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ConversationORM
from backend.embeddings import get_embedder
from backend.models.enums import ConversationStatus, Language
from backend.models.schemas import ConversationRecord, SimilarConversation
from backend.qdrant import get_vector_store


def _tags_to_list(tags: str) -> list[str]:
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def _to_record(c: ConversationORM) -> ConversationRecord:
    return ConversationRecord(
        id=c.id,
        conversation_id=c.conversation_id,
        customer_id=c.customer_id or None,
        agent_name=c.agent_name or None,
        product=c.product or None,
        question=c.question,
        detected_language=Language(c.detected_language)
        if c.detected_language in Language._value2member_map_
        else Language.EN,
        translated_query=c.translated_query,
        final_reply=c.final_reply,
        agent_edited_reply=c.agent_edited_reply or None,
        confidence=c.confidence,
        status=ConversationStatus(c.status)
        if c.status in ConversationStatus._value2member_map_
        else ConversationStatus.ANSWERED,
        favorite=c.favorite,
        pinned=c.pinned,
        tags=_tags_to_list(c.tags),
        response_time_ms=c.response_time_ms,
        created_at=c.created_at,
    )


class HistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        query: str | None = None,
        product: str | None = None,
        agent_name: str | None = None,
        favorite: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ConversationRecord], int]:
        stmt = select(ConversationORM)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                ConversationORM.question.ilike(like)
                | ConversationORM.final_reply.ilike(like)
                | ConversationORM.translated_query.ilike(like)
            )
        if product:
            stmt = stmt.where(ConversationORM.product == product)
        if agent_name:
            stmt = stmt.where(ConversationORM.agent_name == agent_name)
        if favorite is not None:
            stmt = stmt.where(ConversationORM.favorite == favorite)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self.session.execute(count_stmt)).scalar() or 0)

        stmt = stmt.order_by(
            ConversationORM.pinned.desc(), ConversationORM.created_at.desc()
        ).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_record(c) for c in rows], total

    async def semantic_search(
        self, query: str, *, top_k: int = 5, product: str | None = None
    ) -> list[SimilarConversation]:
        embedder = get_embedder()
        store = get_vector_store()
        vector = await embedder.embed_query(query)
        hits = await store.search_conversations(vector, top_k=top_k, product=product)

        results: list[SimilarConversation] = []
        from datetime import datetime

        for h in hits:
            p = h.get("payload", {}) or {}
            raw = p.get("created_at")
            try:
                date = datetime.fromisoformat(raw) if raw else datetime.utcnow()
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

    async def get(self, record_id: int) -> ConversationRecord | None:
        c = await self.session.get(ConversationORM, record_id)
        return _to_record(c) if c else None

    async def update(
        self,
        record_id: int,
        *,
        agent_edited_reply: str | None = None,
        favorite: bool | None = None,
        pinned: bool | None = None,
        status: ConversationStatus | None = None,
        tags: list[str] | None = None,
    ) -> ConversationRecord | None:
        c = await self.session.get(ConversationORM, record_id)
        if c is None:
            return None
        if agent_edited_reply is not None:
            c.agent_edited_reply = agent_edited_reply
        if favorite is not None:
            c.favorite = favorite
        if pinned is not None:
            c.pinned = pinned
        if status is not None:
            c.status = status.value
        if tags is not None:
            c.tags = ",".join(tags)
        await self.session.flush()
        return _to_record(c)

    async def delete(self, record_id: int) -> bool:
        c = await self.session.get(ConversationORM, record_id)
        if c is None:
            return False
        await self.session.delete(c)
        await self.session.flush()
        return True

    async def clear_all(self) -> int:
        result = await self.session.execute(delete(ConversationORM))
        return result.rowcount or 0

    async def export_csv(self) -> str:
        records, _ = await self.list(limit=100000)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "conversation_id", "customer_id", "agent_name", "product",
                "question", "detected_language", "translated_query",
                "final_reply", "agent_edited_reply", "confidence", "status",
                "response_time_ms", "created_at",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.conversation_id, r.customer_id or "", r.agent_name or "",
                    r.product or "", r.question, r.detected_language.value,
                    r.translated_query, r.final_reply, r.agent_edited_reply or "",
                    f"{r.confidence:.2f}", r.status.value, r.response_time_ms,
                    r.created_at.isoformat(),
                ]
            )
        return buf.getvalue()

    async def export_json(self) -> str:
        records, _ = await self.list(limit=100000)
        return json.dumps(
            [json.loads(r.model_dump_json()) for r in records],
            ensure_ascii=False,
            indent=2,
        )
