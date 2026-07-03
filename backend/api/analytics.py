"""Analytics endpoint: GET /api/analytics."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import AnalyticsServiceDep
from backend.models.schemas import AnalyticsResponse
from backend.utils.logging import logger

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(service: AnalyticsServiceDep) -> AnalyticsResponse:
    try:
        return await service.dashboard()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Analytics failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
