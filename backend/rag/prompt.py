"""Prompt construction for grounded Top-3 answer generation."""
from __future__ import annotations

from backend.config import settings
from backend.models.schemas import RetrievedChunk, SimilarConversation

NO_INFO_MESSAGE = (
    "I could not find supporting information inside the uploaded documents."
)

# Kept short — on CPU-only local inference, prompt length drives latency far
# more than output length, so every extra rule here has a real time cost.
SYSTEM_PROMPT = (
    "You help a support agent answer a customer, using ONLY the CONTEXT given. "
    "Never invent facts, numbers, or part names. "
    f"If CONTEXT lacks the answer, set grounded=false and answer exactly: \"{NO_INFO_MESSAGE}\". "
    "Sources are support tickets: 'Opened:' is the customer's QUESTION, 'Closed:' is the "
    "resolution — every answer MUST come from the Closed: text (part numbers, facts). "
    "NEVER restate or paraphrase the Opened:/question text as an answer. "
    "Several sources may share one VIN (same vehicle, different tickets) — answer from "
    "the source whose Opened: question matches what the customer is asking now. "
    "The answer field must ALWAYS be written in English, even if a source's text is in "
    "Japanese or another language — translate the relevant part, never copy non-English "
    "text verbatim. If the Closed: text is already in English, copy it directly (trim "
    "greetings/sign-offs); otherwise give its English translation. Provide up to 3 "
    "alternative answers ranked best-first (fewer is fine if there's only one distinct "
    "answer). Keep each answer under 25 words, no reasoning/explanation. "
    "Cite the source number(s) used per answer. Set confidence in [0,1] for how well the "
    "source supports each answer (high if copied/translated directly). Reply with VALID JSON only."
)

_JSON_SCHEMA_HINT = (
    '{"grounded": true, "suggestions": '
    '[{"answer": "...", "confidence": 0.0, "sources": [1]}]}'
)


def build_context(
    chunks: list[RetrievedChunk], conversations: list[SimilarConversation]
) -> tuple[str, dict[int, RetrievedChunk]]:
    """Return (context_text, source_number -> chunk map)."""
    lines: list[str] = []
    source_map: dict[int, RetrievedChunk] = {}
    remaining = max(settings.max_context_chars, 1000)
    n = 0
    for chunk in chunks:
        if remaining <= 0:
            break
        n += 1
        source_map[n] = chunk
        meta = chunk.metadata
        header = f"[Source {n}] file='{meta.filename}' page={meta.page}"
        if meta.section:
            header += f" section='{meta.section}'"
        text = chunk.text.strip()
        budget = max(0, remaining - len(header) - 2)
        if len(text) > budget:
            text = text[:budget].rsplit(" ", 1)[0].strip()
        lines.append(f"{header}\n{text}")
        remaining -= len(lines[-1]) + 2

    if conversations and remaining > 0:
        lines.append("\n--- Previously answered similar questions (reference only) ---")
        for c in conversations:
            line = (
                f"[Past chat] Q: {c.question}\nA: {c.answer} "
                f"(by {c.agent_name}, similarity={c.similarity:.2f})"
            )
            if len(line) + 2 > remaining:
                break
            lines.append(line)
            remaining -= len(line) + 2

    return "\n\n".join(lines) if lines else "(no context found)", source_map


def build_generation_prompt(query: str, context: str) -> str:
    return (
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {query}\n\n"
        f"Return JSON exactly like: {_JSON_SCHEMA_HINT}"
    )
