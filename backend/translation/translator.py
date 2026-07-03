"""Local translation & language detection.

Two engines:
- ``gemma``  : uses the already-loaded Ollama model. Light on RAM (default).
- ``nllb``   : facebook/nllb-200-distilled-600M via transformers (lazy-loaded).

Language detection uses ``langdetect`` with a Japanese-script fast path.
"""
from __future__ import annotations

import hashlib
import re

from langdetect import DetectorFactory, detect

from backend.config import settings
from backend.llm import get_llm
from backend.models.enums import Language
from backend.utils.cache import TTLCache
from backend.utils.logging import logger

DetectorFactory.seed = 0

# Hiragana, Katakana, common CJK ideographs.
_JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_NLLB_LANG = {Language.EN: "eng_Latn", Language.JA: "jpn_Jpan"}


def detect_language(text: str) -> Language:
    """Detect whether text is Japanese or English."""
    text = (text or "").strip()
    if not text:
        return Language.UNKNOWN
    jp_hits = len(_JP_RE.findall(text))
    if jp_hits and jp_hits >= max(1, len(_LATIN_RE.findall(text))):
        return Language.JA
    if jp_hits:
        return Language.JA
    try:
        code = detect(text)
    except Exception:  # noqa: BLE001
        return Language.EN
    if code == "ja":
        return Language.JA
    return Language.EN


class Translator:
    def __init__(self) -> None:
        self.engine = settings.translation_engine
        self._cache = TTLCache(maxsize=2048, ttl=6 * 3600)
        self._nllb = None  # lazy tuple(tokenizer, model)

    # ---------------- public API ----------------
    async def translate(
        self, text: str, source: Language, target: Language
    ) -> tuple[str, str]:
        """Return (translated_text, engine_used)."""
        text = (text or "").strip()
        if not text:
            return "", self.engine

        if source == Language.AUTO or source == Language.UNKNOWN:
            source = detect_language(text)
        if source == target:
            return text, "passthrough"

        cache_key = hashlib.sha1(
            f"{self.engine}|{source}|{target}|{text}".encode("utf-8")
        ).hexdigest()
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached, self.engine

        if self.engine == "nllb":
            try:
                out = await self._translate_nllb(text, source, target)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"NLLB failed ({exc}); falling back to Gemma.")
                out = await self._translate_gemma(text, source, target)
        else:
            out = await self._translate_gemma(text, source, target)

        await self._cache.set(cache_key, out)
        return out, self.engine

    async def to_english(self, text: str) -> tuple[str, Language]:
        """Translate to English; return (english_text, detected_source)."""
        src = detect_language(text)
        if src == Language.EN:
            return text, src
        translated, _ = await self.translate(text, src, Language.EN)
        return translated, src

    # ---------------- gemma engine ----------------
    async def _translate_gemma(
        self, text: str, source: Language, target: Language
    ) -> str:
        names = {Language.EN: "English", Language.JA: "Japanese"}
        system = (
            "You are a professional translator. Translate the user's text "
            f"from {names[source]} to {names[target]}. "
            "Output ONLY the translation with no explanations, quotes, or notes. "
            "Preserve meaning, tone, numbers, product names and units exactly."
        )
        return await get_llm().generate(text, system=system, temperature=0.0)

    # ---------------- nllb engine ----------------
    def _load_nllb(self):
        if self._nllb is not None:
            return self._nllb
        import torch  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
        )

        logger.info(f"Loading NLLB model: {settings.nllb_model} (first use)")
        tokenizer = AutoTokenizer.from_pretrained(settings.nllb_model)
        model = AutoModelForSeq2SeqLM.from_pretrained(settings.nllb_model)
        device = settings.nllb_device
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        model = model.to(device)
        self._nllb = (tokenizer, model, device)
        return self._nllb

    async def _translate_nllb(
        self, text: str, source: Language, target: Language
    ) -> str:
        import anyio  # noqa: PLC0415

        def _run() -> str:
            tokenizer, model, device = self._load_nllb()
            tokenizer.src_lang = _NLLB_LANG[source]
            inputs = tokenizer(text, return_tensors="pt", truncation=True).to(device)
            bos = tokenizer.convert_tokens_to_ids(_NLLB_LANG[target])
            generated = model.generate(
                **inputs, forced_bos_token_id=bos, max_length=1024
            )
            return tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

        return await anyio.to_thread.run_sync(_run)


_translator: Translator | None = None


def get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
