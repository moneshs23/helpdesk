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
    PPTX = "pptx"
    HTML = "html"
    JSON = "json"
    XML = "xml"
    RTF = "rtf"
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
            "log": cls.TXT,
            "yaml": cls.TXT,
            "yml": cls.TXT,
            "ini": cls.TXT,
            "rst": cls.TXT,
            "csv": cls.CSV,
            "tsv": cls.CSV,
            "xlsx": cls.XLSX,
            "xls": cls.XLSX,
            "xlsm": cls.XLSX,
            "md": cls.MD,
            "markdown": cls.MD,
            "pptx": cls.PPTX,
            "ppt": cls.PPTX,
            "html": cls.HTML,
            "htm": cls.HTML,
            "json": cls.JSON,
            "xml": cls.XML,
            "rtf": cls.RTF,
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
