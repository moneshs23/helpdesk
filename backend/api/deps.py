"""Shared FastAPI dependencies (DB session + service factories)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.services.analytics_service import AnalyticsService
from backend.services.chat_service import ChatService
from backend.services.document_service import DocumentService
from backend.services.history_service import HistoryService
from backend.services.product_service import ProductService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_document_service(session: SessionDep) -> DocumentService:
    return DocumentService(session)


def get_chat_service(session: SessionDep) -> ChatService:
    return ChatService(session)


def get_history_service(session: SessionDep) -> HistoryService:
    return HistoryService(session)


def get_analytics_service(session: SessionDep) -> AnalyticsService:
    return AnalyticsService(session)


def get_product_service() -> ProductService:
    return ProductService()


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
HistoryServiceDep = Annotated[HistoryService, Depends(get_history_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
