"""Shared enumerations."""
from __future__ import annotations

from enum import Enum


class Language(str, Enum):
    JA = "ja"
    EN = "en"
    AUTO = "auto"
    UNKNOWN = "unknown"


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    CSV = "csv"
    XLSX = "xlsx"
    MD = "md"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "DocumentType":
        ext = ext.lower().lstrip(".")
        mapping = {
            "pdf": cls.PDF,
            "docx": cls.DOCX,
            "doc": cls.DOCX,
            "txt": cls.TXT,
            "text": cls.TXT,
            "csv": cls.CSV,
            "xlsx": cls.XLSX,
            "xls": cls.XLSX,
            "md": cls.MD,
            "markdown": cls.MD,
        }
        return mapping.get(ext, cls.UNKNOWN)


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ConversationStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    RESOLVED = "resolved"
