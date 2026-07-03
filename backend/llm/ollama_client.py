"""Ollama LLM client (Gemma 3).

Provides async `generate`, `chat`, streaming, and JSON-structured generation.
The model is configurable at runtime (``set_model``) to satisfy the
"allow changing models later" requirement.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Optional

from ollama import AsyncClient
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.utils.logging import logger


class OllamaLLM:
    def __init__(self) -> None:
        self._client = AsyncClient(host=settings.ollama_base_url)
        self._model = settings.llm_model
        self.keep_alive = settings.llm_keep_alive
        self.default_temperature = settings.llm_temperature
        self.num_ctx = settings.llm_num_ctx
        self.num_predict = settings.llm_num_predict

    @property
    def model(self) -> str:
        return self._model

    def set_model(self, model: str) -> None:
        logger.info(f"Switching LLM model: {self._model} -> {model}")
        self._model = model

    def _options(self, temperature: Optional[float], **extra: Any) -> dict:
        opts = {
            "temperature": self.default_temperature if temperature is None else temperature,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
        }
        opts.update(extra)
        return opts

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=4))
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **options: Any,
    ) -> str:
        resp = await self._client.generate(
            model=self._model,
            prompt=prompt,
            system=system,
            options=self._options(temperature, **options),
            keep_alive=self.keep_alive,
        )
        return resp.get("response", "").strip()

    async def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **options: Any,
    ) -> dict:
        """Generate a response constrained to JSON and parse it."""
        resp = await self._client.generate(
            model=self._model,
            prompt=prompt,
            system=system,
            format="json",
            options=self._options(temperature, **options),
            keep_alive=self.keep_alive,
        )
        raw = resp.get("response", "").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            cleaned = _extract_json(raw)
            if cleaned is not None:
                return cleaned
            logger.warning("LLM JSON parse failed; returning empty object.")
            return {}

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        **options: Any,
    ) -> str:
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            options=self._options(temperature, **options),
            keep_alive=self.keep_alive,
        )
        return resp.get("message", {}).get("content", "").strip()

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **options: Any,
    ) -> AsyncIterator[str]:
        async for part in await self._client.generate(
            model=self._model,
            prompt=prompt,
            system=system,
            options=self._options(temperature, **options),
            keep_alive=self.keep_alive,
            stream=True,
        ):
            chunk = part.get("response", "")
            if chunk:
                yield chunk

    async def health(self) -> bool:
        try:
            await self.generate("ping", temperature=0.0, num_predict=1)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM health check failed: {exc}")
            return False


def _extract_json(raw: str) -> Optional[dict]:
    """Best-effort JSON extraction, including repair of truncated output."""
    start = raw.find("{")
    if start == -1:
        return None
    snippet = raw[start:]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        pass
    # Repair truncated JSON: cut to the last complete object, then re-balance
    # any still-open arrays/objects (keeps earlier complete suggestions).
    last = snippet.rfind("}")
    if last != -1:
        candidate = snippet[: last + 1]
        opens = candidate.count("{") - candidate.count("}")
        brackets = candidate.count("[") - candidate.count("]")
        candidate += "]" * max(0, brackets) + "}" * max(0, opens)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
    return None


_llm: OllamaLLM | None = None


def get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM()
    return _llm
