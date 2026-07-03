"""Prompt construction for grounded Top-3 answer generation."""
from __future__ import annotations

from backend.models.schemas import RetrievedChunk, SimilarConversation

NO_INFO_MESSAGE = (
    "I could not find supporting information inside the uploaded documents."
)

SYSTEM_PROMPT = (
    "You are an assistant that helps a human customer-support agent draft replies. "
    "You DO NOT talk to the customer directly; you only assist the agent.\n\n"
    "STRICT RULES:\n"
    "1. Answer ONLY using the provided CONTEXT sources. Never use outside knowledge.\n"
    "2. NEVER invent facts, numbers, prices, policies, or part names.\n"
    "3. If the context does not contain the answer, set \"grounded\" to false and use "
    f"exactly this text for every answer: \"{NO_INFO_MESSAGE}\".\n"
    "4. Every answer must be supported by at least one source; list the source numbers you used.\n"
    "5. Provide exactly 3 alternative answers ranked best-first. Keep each answer "
    "concise (under 60 words), professional, and in English.\n"
    "6. Give an honest confidence score in [0,1] based on how well the context supports the answer.\n"
    "7. Respond with VALID JSON only, matching the required schema."
)

_JSON_SCHEMA_HINT = (
    "{\n"
    '  "grounded": true,\n'
    '  "suggestions": [\n'
    '    {"answer": "...", "confidence": 0.0, "reasoning": "...", "sources": [1, 2]}\n'
    "  ]\n"
    "}"
)


def build_context(
    chunks: list[RetrievedChunk], conversations: list[SimilarConversation]
) -> tuple[str, dict[int, RetrievedChunk]]:
    """Return (context_text, source_number -> chunk map)."""
    lines: list[str] = []
    source_map: dict[int, RetrievedChunk] = {}
    n = 0
    for chunk in chunks:
        n += 1
        source_map[n] = chunk
        meta = chunk.metadata
        header = f"[Source {n}] file='{meta.filename}' page={meta.page}"
        if meta.section:
            header += f" section='{meta.section}'"
        lines.append(f"{header}\n{chunk.text.strip()}")

    if conversations:
        lines.append("\n--- Previously answered similar questions (reference only) ---")
        for c in conversations:
            lines.append(
                f"[Past chat] Q: {c.question}\nA: {c.answer} "
                f"(by {c.agent_name}, similarity={c.similarity:.2f})"
            )

    return "\n\n".join(lines) if lines else "(no context found)", source_map


def build_generation_prompt(query: str, context: str) -> str:
    return (
        f"CONTEXT:\n{context}\n\n"
        f"AGENT'S CUSTOMER QUESTION (in English):\n{query}\n\n"
        "TASK: Draft the 3 best suggested replies for the agent, grounded strictly in the "
        "CONTEXT above. Cite the source numbers you used for each reply.\n\n"
        f"Return JSON EXACTLY in this shape:\n{_JSON_SCHEMA_HINT}"
    )
