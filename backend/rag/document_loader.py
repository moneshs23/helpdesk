"""Text extraction from supported document formats.

Each loader returns a list of ``PageText`` items carrying page/section context so
that downstream chunks can be cited precisely (filename + page + section).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chardet

from backend.config import settings
from backend.models.enums import DocumentType
from backend.utils.logging import logger


@dataclass
class PageText:
    page: int
    section: str
    text: str


# ---------------- individual extractors ----------------
def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _decode(data: bytes) -> str:
    guess = chardet.detect(data)
    encoding = guess.get("encoding") or "utf-8"
    try:
        return data.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return data.decode("utf-8", errors="replace")


def load_txt(path: Path) -> list[PageText]:
    return [PageText(page=1, section="", text=_decode(_read_bytes(path)))]


def load_md(path: Path) -> list[PageText]:
    text = _decode(_read_bytes(path))
    pages: list[PageText] = []
    current_section = ""
    buffer: list[str] = []
    page_no = 1
    for line in text.splitlines():
        if line.startswith("#"):
            if buffer:
                pages.append(
                    PageText(page_no, current_section, "\n".join(buffer).strip())
                )
                buffer = []
                page_no += 1
            current_section = line.lstrip("# ").strip()
        buffer.append(line)
    if buffer:
        pages.append(PageText(page_no, current_section, "\n".join(buffer).strip()))
    return pages or [PageText(1, "", text)]


def load_pdf(path: Path) -> list[PageText]:
    from pypdf import PdfReader  # noqa: PLC0415

    reader = PdfReader(str(path))
    pages: list[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text and settings.enable_ocr:
            text = _ocr_pdf_page(path, i - 1)
        if text:
            pages.append(PageText(page=i, section="", text=text))
    return pages


def _ocr_pdf_page(path: Path, page_index: int) -> str:
    """Best-effort OCR for scanned PDF pages (requires tesseract + pdf2image)."""
    try:
        import pytesseract  # noqa: PLC0415
        from pdf2image import convert_from_path  # noqa: PLC0415

        images = convert_from_path(
            str(path), first_page=page_index + 1, last_page=page_index + 1, dpi=200
        )
        if images:
            return pytesseract.image_to_string(images[0]).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"OCR failed for {path.name} page {page_index + 1}: {exc}")
    return ""


def load_docx(path: Path) -> list[PageText]:
    from docx import Document as DocxDocument  # noqa: PLC0415

    doc = DocxDocument(str(path))
    pages: list[PageText] = []
    current_section = ""
    buffer: list[str] = []
    page_no = 1
    for para in doc.paragraphs:
        style = (para.style.name or "").lower() if para.style else ""
        if style.startswith("heading"):
            if buffer:
                pages.append(
                    PageText(page_no, current_section, "\n".join(buffer).strip())
                )
                buffer = []
                page_no += 1
            current_section = para.text.strip()
        if para.text.strip():
            buffer.append(para.text.strip())
    # Tables
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                buffer.append(" | ".join(cells))
    if buffer:
        pages.append(PageText(page_no, current_section, "\n".join(buffer).strip()))
    return pages or [PageText(1, "", "")]


def load_csv(path: Path) -> list[PageText]:
    import pandas as pd  # noqa: PLC0415

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return _dataframe_to_pages(df, section="CSV data")


def load_xlsx(path: Path) -> list[PageText]:
    import pandas as pd  # noqa: PLC0415

    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    pages: list[PageText] = []
    for i, (name, df) in enumerate(sheets.items(), start=1):
        df = df.fillna("")
        rows = _rows_to_text(df)
        if rows:
            pages.append(PageText(page=i, section=f"Sheet: {name}", text=rows))
    return pages or [PageText(1, "", "")]


def _dataframe_to_pages(df, section: str) -> list[PageText]:
    text = _rows_to_text(df)
    return [PageText(page=1, section=section, text=text)] if text else [PageText(1, section, "")]


def _rows_to_text(df) -> str:
    headers = list(df.columns)
    lines = []
    for _, row in df.iterrows():
        parts = [f"{h}: {row[h]}" for h in headers if str(row[h]).strip()]
        if parts:
            lines.append("; ".join(parts))
    return "\n".join(lines)


_LOADERS = {
    DocumentType.TXT: load_txt,
    DocumentType.MD: load_md,
    DocumentType.PDF: load_pdf,
    DocumentType.DOCX: load_docx,
    DocumentType.CSV: load_csv,
    DocumentType.XLSX: load_xlsx,
}


def load_document(path: Path, doc_type: DocumentType) -> list[PageText]:
    loader = _LOADERS.get(doc_type)
    if loader is None:
        raise ValueError(f"No loader for document type: {doc_type}")
    pages = loader(path)
    return [p for p in pages if p.text and p.text.strip()]
