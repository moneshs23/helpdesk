"""Security helpers: filename sanitization, upload validation, prompt-injection defense."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from slugify import slugify

from backend.config import settings
from backend.models.enums import DocumentType

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "csv", "xlsx", "xls", "md", "markdown"}

# Patterns commonly used in prompt-injection / jailbreak attempts.
_INJECTION_PATTERNS = [
    r"ignore (all|any|the) (previous|prior|above) (instructions|prompts?)",
    r"disregard (all|any|the) (previous|prior|above)",
    r"forget (all|everything|your) (instructions|rules)",
    r"you are now",
    r"system prompt",
    r"reveal your (system )?prompt",
    r"act as (an?|the) (dan|jailbreak)",
    r"</?(system|assistant|user)>",
    r"\bBEGIN SYSTEM\b",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


class ValidationError(Exception):
    """Raised when an upload fails validation."""


def sanitize_filename(filename: str) -> str:
    """Return a safe filename, preserving the extension."""
    filename = unicodedata.normalize("NFKC", filename or "file")
    name = Path(filename).name  # strip any path components
    stem = Path(name).stem
    ext = Path(name).suffix.lower().lstrip(".")
    safe_stem = slugify(stem, max_length=100) or "document"
    if ext:
        return f"{safe_stem}.{ext}"
    return safe_stem


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def validate_upload(filename: str, size_bytes: int) -> DocumentType:
    """Validate extension and size; return the resolved DocumentType."""
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if size_bytes <= 0:
        raise ValidationError("Empty file.")
    if size_bytes > settings.max_upload_bytes:
        raise ValidationError(
            f"File too large ({size_bytes / 1e6:.1f} MB). Max is {settings.max_upload_mb} MB."
        )
    return DocumentType.from_extension(ext)


def detect_prompt_injection(text: str) -> bool:
    """Heuristic detection of prompt-injection attempts in user input."""
    return bool(_INJECTION_RE.search(text or ""))


def neutralize_injection(text: str) -> str:
    """Neutralize role-tag style injections without dropping user content."""
    cleaned = re.sub(r"</?(system|assistant|user)\s*>", " ", text or "", flags=re.IGNORECASE)
    return cleaned.strip()
