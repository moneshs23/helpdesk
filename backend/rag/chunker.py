"""Intelligent text chunking with overlap.

Splits on paragraph/sentence boundaries where possible, respecting a target
character budget with configurable overlap for retrieval continuity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.config import settings
from backend.rag.document_loader import PageText

_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|\n{2,}")


@dataclass
class Chunk:
    text: str
    page: int
    section: str
    index: int


def _split_units(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def _chunk_text(
    text: str, size: int, overlap: int
) -> list[str]:
    units = _split_units(text)
    if not units:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        unit_len = len(unit)
        if current_len + unit_len > size and current:
            chunks.append(" ".join(current).strip())
            # start new chunk with overlap tail
            tail: list[str] = []
            tail_len = 0
            for prev in reversed(current):
                if tail_len + len(prev) > overlap:
                    break
                tail.insert(0, prev)
                tail_len += len(prev)
            current = tail
            current_len = tail_len
        # A single very long unit gets hard-split.
        if unit_len > size:
            for start in range(0, unit_len, size - overlap):
                chunks.append(unit[start : start + size].strip())
            current, current_len = [], 0
            continue
        current.append(unit)
        current_len += unit_len
    if current:
        chunks.append(" ".join(current).strip())
    return [c for c in chunks if c]


def chunk_pages(
    pages: list[PageText],
    size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap
    chunks: list[Chunk] = []
    index = 0
    for page in pages:
        for piece in _chunk_text(page.text, size, overlap):
            chunks.append(
                Chunk(text=piece, page=page.page, section=page.section, index=index)
            )
            index += 1
    return chunks
