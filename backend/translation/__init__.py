"""Local translation (NLLB-200 / Gemma fallback)."""
from backend.translation.translator import (
    Translator,
    detect_language,
    get_translator,
)

__all__ = ["Translator", "detect_language", "get_translator"]
