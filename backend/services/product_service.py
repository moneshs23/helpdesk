"""Product information service (grounded search over uploaded documents)."""
from __future__ import annotations

from backend.llm import get_llm
from backend.models.schemas import ProductSearchResponse, RetrievedChunk
from backend.rag.prompt import NO_INFO_MESSAGE
from backend.rag.retriever import retrieve_documents

# Product-intent keywords per the spec.
PRODUCT_INTENTS = [
    "price", "warranty", "spare part", "spare parts", "maintenance",
    "installation", "safety", "repair", "return policy", "return",
]


def is_product_query(text: str) -> bool:
    low = (text or "").lower()
    return any(intent in low for intent in PRODUCT_INTENTS)


class ProductService:
    async def search(
        self, query: str, *, product: str | None = None, top_k: int = 6
    ) -> ProductSearchResponse:
        chunks: list[RetrievedChunk] = await retrieve_documents(
            query, top_k=top_k, product=product
        )
        if not chunks:
            return ProductSearchResponse(
                query=query, grounded=False, answer=NO_INFO_MESSAGE, chunks=[]
            )

        context = "\n\n".join(
            f"[Source {i}] file='{c.metadata.filename}' page={c.metadata.page}\n{c.text}"
            for i, c in enumerate(chunks, start=1)
        )
        system = (
            "Answer the product question using ONLY the provided context. "
            "If the answer is not in the context, reply EXACTLY: "
            f"'{NO_INFO_MESSAGE}'. Cite file names. Be concise and factual."
        )
        prompt = f"CONTEXT:\n{context}\n\nQUESTION: {query}\n\nANSWER:"
        answer = await get_llm().generate(prompt, system=system, temperature=0.0)
        grounded = NO_INFO_MESSAGE not in answer
        return ProductSearchResponse(
            query=query, grounded=grounded, answer=answer.strip(), chunks=chunks
        )
