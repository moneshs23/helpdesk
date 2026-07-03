"""Chat endpoint: POST /api/chat."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import ChatServiceDep
from backend.models.schemas import ChatRequest, ChatResponse
from backend.utils.logging import logger

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, service: ChatServiceDep) -> ChatResponse:
    try:
        return await service.process(request)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat processing failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}") from exc
