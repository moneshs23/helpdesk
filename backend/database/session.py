"""Async SQLAlchemy engine & session management."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from backend.config import settings
from backend.database.models import Base
from backend.utils.logging import logger

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    poolclass=NullPool,
    connect_args={"check_same_thread": False, "timeout": 15},
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enable WAL mode so readers never block a writer (fixes 'database is locked')."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create tables if they do not exist, then run lightweight migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate)
    logger.info("SQLite database initialized.")


def _migrate(conn) -> None:
    """Add columns introduced after the first release (SQLite-safe)."""
    from sqlalchemy import text

    existing = {
        row[1] for row in conn.execute(text("PRAGMA table_info(conversations)"))
    }
    additions = {
        "customer_reply": "TEXT DEFAULT ''",
        "source": "VARCHAR(16) DEFAULT 'agent'",
        "answered_at": "DATETIME",
    }
    for column, ddl in additions.items():
        if column not in existing:
            conn.execute(
                text(f"ALTER TABLE conversations ADD COLUMN {column} {ddl}")
            )
            logger.info(f"Migrated: added conversations.{column}")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
