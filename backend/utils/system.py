"""System / dependency health checks (Ollama, models, storage)."""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from backend.config import settings
from backend.utils.logging import logger


@dataclass
class ComponentStatus:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SystemHealth:
    ok: bool
    components: list[ComponentStatus] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "components": [c.__dict__ for c in self.components],
        }


async def check_ollama() -> list[ComponentStatus]:
    """Verify Ollama is reachable and required models are present."""
    results: list[ComponentStatus] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            tags = {m.get("name", "") for m in resp.json().get("models", [])}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Ollama not reachable: {exc}")
        return [ComponentStatus("ollama", False, f"unreachable: {exc}")]

    results.append(ComponentStatus("ollama", True, "reachable"))

    def _has(model: str) -> bool:
        base = model.split(":")[0]
        return any(t == model or t.split(":")[0] == base for t in tags)

    results.append(
        ComponentStatus(
            f"llm:{settings.llm_model}",
            _has(settings.llm_model),
            "present" if _has(settings.llm_model) else "missing — run `ollama pull`",
        )
    )
    results.append(
        ComponentStatus(
            f"embed:{settings.embedding_model}",
            _has(settings.embedding_model),
            "present" if _has(settings.embedding_model) else "missing — run `ollama pull`",
        )
    )
    return results


async def get_system_health() -> SystemHealth:
    components = await check_ollama()
    ok = all(c.ok for c in components)
    return SystemHealth(ok=ok, components=components)
