"""Application configuration.

All settings are loaded from environment variables (see `.env.example`).
This module exposes a cached `get_settings()` accessor so the configuration is
parsed once and injected everywhere via FastAPI's dependency system.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (backend/config/settings.py -> repo root)
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "AI Customer Support Assistant"
    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "*"

    # ---- Ollama ----
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "gemma3:4b"
    llm_temperature: float = 0.2
    llm_num_ctx: int = 4096
    llm_num_predict: int = 768
    llm_keep_alive: str = "30m"
    enable_query_rewrite: bool = False

    # ---- Embeddings ----
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    embedding_batch_size: int = 16

    # ---- Qdrant ----
    qdrant_mode: Literal["local", "server"] = "local"
    qdrant_path: str = "./data/qdrant"
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    qdrant_docs_collection: str = "documents"
    qdrant_chats_collection: str = "conversations"

    # ---- Database ----
    database_url: str = "sqlite+aiosqlite:///./data/sqlite/app.db"

    # ---- Translation ----
    translation_engine: Literal["gemma", "nllb"] = "gemma"
    nllb_model: str = "facebook/nllb-200-distilled-600M"
    nllb_device: str = "auto"

    # ---- RAG ----
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k_docs: int = 6
    top_k_chats: int = 4
    min_score_threshold: float = 0.6
    hybrid_alpha: float = 0.5

    # ---- Neo4j (optional graph retrieval) ----
    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    graph_retrieval_weight: float = 0.3  # weight for graph results when merging

    # ---- Uploads ----
    upload_dir: str = "./uploads"
    max_upload_mb: int = 25
    enable_ocr: bool = False

    # ---- Security ----
    rate_limit_per_minute: int = 60
    log_level: str = "INFO"

    # ---------- Derived / helper properties ----------
    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = (ROOT_DIR / self.upload_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def qdrant_local_path(self) -> Path:
        p = (ROOT_DIR / self.qdrant_path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_overlap(cls, v: int, info) -> int:
        size = info.data.get("chunk_size", 800)
        if v >= size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    settings = Settings()
    # Ensure the SQLite directory exists for the configured database URL.
    if settings.database_url.startswith("sqlite"):
        db_file = settings.database_url.split("///")[-1]
        (ROOT_DIR / db_file).parent.mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "history").mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
