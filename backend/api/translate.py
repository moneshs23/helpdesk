"""Translation endpoint: POST /api/translate."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import TranslateRequest, TranslateResponse
from backend.translation import detect_language, get_translator
from backend.utils.logging import logger

router = APIRouter(prefix="/api", tags=["translation"])


@router.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest) -> TranslateResponse:
    try:
        translator = get_translator()
        source = (
            detect_language(request.text)
            if request.source.value in ("auto", "unknown")
            else request.source
        )
        translated, engine = await translator.translate(
            request.text, source, request.target
        )
        return TranslateResponse(
            source_language=source,
            target_language=request.target,
            original=request.text,
            translated=translated,
            engine=engine,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Translation failed")
        raise HTTPException(status_code=500, detail=f"Translation failed: {exc}") from exc
