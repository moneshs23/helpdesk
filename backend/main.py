"""FastAPI application entrypoint — wires config, middleware, and all routers."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.api import (
    analytics,
    chat,
    documents,
    history,
    products,
    system,
    translate,
    upload,
)
from backend.config import ROOT_DIR, settings
from backend.database import init_db
from backend.utils.logging import configure_logging, logger

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(f"Starting {settings.app_name} (env={settings.app_env})")
    logger.info(f"LLM model: {settings.llm_model} @ {settings.ollama_base_url}")
    await init_db()
    # Warm the vector store (creates collections) without blocking startup hard.
    try:
        from backend.qdrant import get_vector_store

        get_vector_store()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Vector store init deferred: {exc}")
    # Warm up the LLM + embedder in the background so the first user query is fast.
    asyncio.create_task(_warmup())
    yield
    logger.info("Shutting down.")


async def _warmup() -> None:
    try:
        from backend.embeddings import get_embedder
        from backend.llm import get_llm

        await get_embedder().embed_query("warmup")
        await get_llm().generate("Hi", temperature=0.0, num_predict=1)
        logger.info("Model warmup complete.")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Warmup skipped: {exc}")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Local, offline, multilingual AI assistant for support agents.",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled error on {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )

    @app.get("/api/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok"}

    # Feature routers
    for module in (
        upload, chat, documents, history, translate, products, analytics, system
    ):
        app.include_router(module.router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built frontend (frontend/dist) in production, if present."""
    dist = Path(ROOT_DIR) / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
        logger.info(f"Serving frontend from {dist}")
    else:
        @app.get("/", tags=["meta"])
        async def root() -> dict:
            return {
                "app": settings.app_name,
                "version": "0.1.0",
                "status": "ok",
                "docs": "/docs",
                "note": "Frontend not built yet. Run `make frontend` for dev mode.",
            }


app = create_app()
