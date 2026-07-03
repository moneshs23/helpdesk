"""Upload endpoint: POST /api/upload."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.api.deps import DocumentServiceDep
from backend.models.schemas import UploadResponse
from backend.utils.logging import logger
from backend.utils.security import ValidationError

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    service: DocumentServiceDep,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    product: str = Form(""),
    tags: str = Form(""),
) -> UploadResponse:
    content = await file.read()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        doc = await service.upload(
            content=content,
            filename=file.filename or "document",
            title=title,
            product=product,
            tags=tag_list,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    return UploadResponse(document=doc)
