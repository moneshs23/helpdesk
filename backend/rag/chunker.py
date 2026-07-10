"""Intelligent text chunking with overlap.

Splits on paragraph/sentence boundaries where possible, respecting a target
character budget with configurable overlap for retrieval continuity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.config import settings
from backend.rag.document_loader import PageText

_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+")


@dataclass
class Chunk:
    text: str
    page: int
    section: str
    index: int


def _split_units(text: str) -> list[str]:
    """Split text into line-then-sentence units.

    Lines are the primary boundary so row-oriented content (Excel/CSV rows,
    lists, logs) without sentence punctuation never collapses into one
    oversized block that would be hard-split mid-row.
    """
    units: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        units.extend(p.strip() for p in _SENTENCE_RE.split(line) if p.strip())
    return units


def _chunk_text(
    text: str, size: int, overlap: int
) -> list[str]:
    units = _split_units(text)
    if not units:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    step = max(size - overlap, 1)
    for unit in units:
        unit_len = len(unit)
        if current_len + unit_len > size and current:
            chunks.append("\n".join(current).strip())
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
            for start in range(0, unit_len, step):
                chunks.append(unit[start : start + size].strip())
            current, current_len = [], 0
            continue
        current.append(unit)
        current_len += unit_len
    if current:
        chunks.append("\n".join(current).strip())
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
        if page.row_oriented:
            # One row/record = one chunk, always. Never merge neighboring rows
            # into the same chunk and never split a row across chunks — each
            # row must retrieve as a complete, self-contained answer.
            for line in page.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                chunks.append(
                    Chunk(text=line, page=page.page, section=page.section, index=index)
                )
                index += 1
            continue
        for piece in _chunk_text(page.text, size, overlap):
            chunks.append(
                Chunk(text=piece, page=page.page, section=page.section, index=index)
            )
            index += 1
    return chunks
