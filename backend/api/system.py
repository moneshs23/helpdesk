"""System endpoints: health, models list, model switching, settings."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.llm import get_llm
from backend.utils.logging import logger
from backend.utils.system import get_system_health

router = APIRouter(prefix="/api", tags=["system"])


class ModelInfo(BaseModel):
    name: str
    size: int = 0


class SelectModelRequest(BaseModel):
    model: str


@router.get("/system")
async def system() -> dict:
    health = await get_system_health()
    return health.as_dict()


@router.get("/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
        return [
            ModelInfo(name=m.get("name", ""), size=m.get("size", 0)) for m in models
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not list models: {exc}")
        raise HTTPException(status_code=503, detail="Ollama unreachable") from exc


@router.post("/models/select")
async def select_model(body: SelectModelRequest) -> dict:
    get_llm().set_model(body.model)
    return {"message": f"Active model set to {body.model}", "model": body.model}


@router.get("/settings")
async def get_public_settings() -> dict:
    llm = get_llm()
    return {
        "app_name": settings.app_name,
        "active_model": llm.model,
        "embedding_model": settings.embedding_model,
        "translation_engine": settings.translation_engine,
        "max_upload_mb": settings.max_upload_mb,
        "supported_types": ["pdf", "docx", "txt", "csv", "xlsx", "md"],
    }
