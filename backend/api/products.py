"""Product search endpoint: POST /api/products."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import ProductServiceDep
from backend.models.schemas import ProductSearchRequest, ProductSearchResponse
from backend.utils.logging import logger

router = APIRouter(prefix="/api", tags=["products"])


@router.post("/products", response_model=ProductSearchResponse)
async def product_search(
    request: ProductSearchRequest, service: ProductServiceDep
) -> ProductSearchResponse:
    try:
        return await service.search(
            request.query, product=request.product, top_k=request.top_k
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Product search failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
