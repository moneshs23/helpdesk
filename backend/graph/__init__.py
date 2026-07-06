"""Neo4j graph store for relationship-aware retrieval.

Optional module — only active when NEO4J_ENABLED=true in settings.
Falls back gracefully so the rest of the system is unaffected.
"""
from __future__ import annotations

from typing import Optional

from backend.config import settings
from backend.utils.logging import logger

_store: Optional["GraphStore"] = None


def get_graph_store() -> Optional["GraphStore"]:
    """Return a cached GraphStore instance, or None if Neo4j is disabled."""
    global _store
    if not settings.neo4j_enabled:
        return None
    if _store is None:
        from backend.graph.graph_store import GraphStore

        try:
            _store = GraphStore()
            logger.info("Neo4j graph store initialised")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Neo4j unavailable, falling back to vector-only: {exc}")
            return None
    return _store
