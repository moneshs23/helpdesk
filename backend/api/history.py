"""Conversation history endpoints: GET /api/history (+ search, update, export)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from backend.api.deps import HistoryServiceDep
from backend.models.schemas import (
    ConversationRecord,
    HistoryResponse,
    MessageResponse,
    SimilarConversation,
    UpdateConversationRequest,
)

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    service: HistoryServiceDep,
    query: str | None = Query(None),
    product: str | None = Query(None),
    agent_name: str | None = Query(None),
    favorite: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> HistoryResponse:
    records, total = await service.list(
        query=query,
        product=product,
        agent_name=agent_name,
        favorite=favorite,
        limit=limit,
        offset=offset,
    )
    return HistoryResponse(conversations=records, total=total)


@router.get("/history/search", response_model=list[SimilarConversation])
async def semantic_history_search(
    service: HistoryServiceDep,
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    product: str | None = Query(None),
) -> list[SimilarConversation]:
    return await service.semantic_search(query, top_k=top_k, product=product)


@router.get("/history/export.csv", response_class=PlainTextResponse)
async def export_csv(service: HistoryServiceDep) -> PlainTextResponse:
    data = await service.export_csv()
    return PlainTextResponse(
        data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=conversations.csv"},
    )


@router.get("/history/export.json", response_class=PlainTextResponse)
async def export_json(service: HistoryServiceDep) -> PlainTextResponse:
    data = await service.export_json()
    return PlainTextResponse(
        data,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=conversations.json"},
    )


@router.get("/history/{record_id}", response_model=ConversationRecord)
async def get_conversation(
    record_id: int, service: HistoryServiceDep
) -> ConversationRecord:
    record = await service.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return record


@router.patch("/history/{record_id}", response_model=ConversationRecord)
async def update_conversation(
    record_id: int,
    body: UpdateConversationRequest,
    service: HistoryServiceDep,
) -> ConversationRecord:
    record = await service.update(
        record_id,
        agent_edited_reply=body.agent_edited_reply,
        favorite=body.favorite,
        pinned=body.pinned,
        status=body.status,
        tags=body.tags,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return record


@router.delete("/history/{record_id}", response_model=MessageResponse)
async def delete_conversation(
    record_id: int, service: HistoryServiceDep
) -> MessageResponse:
    ok = await service.delete(record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return MessageResponse(message="Conversation deleted.")
