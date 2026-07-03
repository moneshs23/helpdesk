"""Analytics service: dashboard statistics."""
from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ConversationORM, DocumentORM
from backend.models.enums import ConversationStatus
from backend.models.schemas import (
    AgentCount,
    AnalyticsResponse,
    ProductCount,
)
from backend.services.document_service import DocumentService


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dashboard(self) -> AnalyticsResponse:
        today_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
        )

        todays = int(
            (
                await self.session.execute(
                    select(func.count(ConversationORM.id)).where(
                        ConversationORM.created_at >= today_start
                    )
                )
            ).scalar()
            or 0
        )
        total = int(
            (await self.session.execute(select(func.count(ConversationORM.id)))).scalar()
            or 0
        )
        avg_rt = float(
            (
                await self.session.execute(
                    select(func.avg(ConversationORM.response_time_ms))
                )
            ).scalar()
            or 0.0
        )
        docs = int(
            (await self.session.execute(select(func.count(DocumentORM.id)))).scalar() or 0
        )
        total_chunks = int(
            (await self.session.execute(select(func.sum(DocumentORM.chunk_count)))).scalar()
            or 0
        )
        pending = int(
            (
                await self.session.execute(
                    select(func.count(ConversationORM.id)).where(
                        ConversationORM.status == ConversationStatus.PENDING.value
                    )
                )
            ).scalar()
            or 0
        )

        products = await self._top_products()
        agents = await self._top_agents()
        recent = await DocumentService(self.session).recent(limit=5)

        return AnalyticsResponse(
            todays_queries=todays,
            total_queries=total,
            avg_response_time_ms=round(avg_rt, 1),
            documents_uploaded=docs,
            total_chunks=total_chunks,
            most_asked_products=products,
            top_agents=agents,
            pending_queries=pending,
            recent_uploads=recent,
        )

    async def _top_products(self, limit: int = 5) -> list[ProductCount]:
        stmt = (
            select(ConversationORM.product, func.count(ConversationORM.id))
            .where(ConversationORM.product != "")
            .group_by(ConversationORM.product)
            .order_by(func.count(ConversationORM.id).desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [ProductCount(product=p, count=c) for p, c in rows]

    async def _top_agents(self, limit: int = 5) -> list[AgentCount]:
        stmt = (
            select(ConversationORM.agent_name, func.count(ConversationORM.id))
            .where(ConversationORM.agent_name != "")
            .group_by(ConversationORM.agent_name)
            .order_by(func.count(ConversationORM.id).desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [AgentCount(agent_name=a, count=c) for a, c in rows]
