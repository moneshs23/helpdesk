"""Neo4j-backed graph store for relationship-aware document retrieval.

Creates a knowledge graph from documents and conversations, enabling
graph traversal to find contextually related chunks that pure vector
similarity would miss (e.g., product→accessory relationships, escalation
paths, cross-referenced policies).

Node types:
- Document  (id, filename, title)
- Chunk     (id, text_preview, page, section)
- Product   (name)
- Topic     (name)
- Agent     (name)
- Conversation (id, question, answer)

Relationships:
- (Document)-[:CONTAINS]->(Chunk)
- (Chunk)-[:MENTIONS]->(Product|Topic)
- (Chunk)-[:RELATED_TO]->(Chunk)         — co-occurring entities
- (Conversation)-[:ABOUT]->(Product)
- (Conversation)-[:ANSWERED_BY]->(Agent)
"""
from __future__ import annotations

import re
from typing import Any, Optional

import anyio
from neo4j import GraphDatabase

from backend.config import settings
from backend.utils.logging import logger


# Simple keyword-based entity extraction (fast, works offline on M1 8GB).
_PRODUCT_PATTERN = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9]*[-\s]?(?:Pro|Max|Plus|Ultra|Lite|Air|SE|XR|XS)?)\b"
)


def _extract_entities(text: str) -> dict[str, list[str]]:
    """Extract product names and topics from text using keyword heuristics."""
    products: set[str] = set()
    topics: set[str] = set()

    # Products: capitalized compound words that look like product names
    for m in _PRODUCT_PATTERN.finditer(text):
        candidate = m.group().strip()
        if len(candidate) >= 3 and candidate not in {
            "The", "This", "That", "What", "When", "Where", "How", "Why",
            "Please", "Thank", "Hello", "Source", "Note", "Context",
        }:
            products.add(candidate)

    # Topics: extract from section headers, bold markers, or key phrases
    for line in text.split("\n"):
        stripped = line.strip()
        # Markdown headers
        if stripped.startswith("#"):
            topic = stripped.lstrip("#").strip().rstrip(":")
            if 3 <= len(topic) <= 80:
                topics.add(topic)
        # Lines ending with colon (common in manuals/FAQs)
        elif stripped.endswith(":") and len(stripped) < 80:
            topics.add(stripped.rstrip(":").strip())

    return {"products": list(products)[:10], "topics": list(topics)[:10]}


class GraphStore:
    """Wraps Neo4j driver with document/conversation graph operations."""

    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify connectivity.
        self._driver.verify_connectivity()
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create full-text and uniqueness indexes if they don't exist."""
        with self._driver.session() as session:
            # Uniqueness constraints
            for label, prop in [
                ("Document", "doc_id"),
                ("Product", "name"),
                ("Topic", "name"),
                ("Agent", "name"),
            ]:
                try:
                    session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    )
                except Exception:  # noqa: BLE001
                    pass

            # Full-text index on Chunk text for Cypher full-text search
            try:
                session.run(
                    "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS "
                    "FOR (n:Chunk) ON EACH [n.text_preview]"
                )
            except Exception:  # noqa: BLE001
                pass

    def close(self) -> None:
        self._driver.close()

    # ------------------------------------------------------------------ #
    #  Indexing
    # ------------------------------------------------------------------ #
    def _index_document_sync(
        self,
        doc_id: str,
        filename: str,
        title: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        """Index a document and its chunks into the graph."""
        with self._driver.session() as session:
            # Create Document node
            session.run(
                "MERGE (d:Document {doc_id: $doc_id}) "
                "SET d.filename = $filename, d.title = $title",
                doc_id=doc_id, filename=filename, title=title,
            )

            for chunk in chunks:
                chunk_id = chunk.get("chunk_id", "")
                text = chunk.get("text", "")
                page = chunk.get("page", 0)
                section = chunk.get("section", "")
                preview = text[:500]

                # Create Chunk node and link to Document
                session.run(
                    "MATCH (d:Document {doc_id: $doc_id}) "
                    "MERGE (c:Chunk {chunk_id: $chunk_id}) "
                    "SET c.text_preview = $preview, c.page = $page, c.section = $section "
                    "MERGE (d)-[:CONTAINS]->(c)",
                    doc_id=doc_id, chunk_id=chunk_id, preview=preview,
                    page=page, section=section,
                )

                # Extract and link entities
                entities = _extract_entities(text)
                for product in entities["products"]:
                    session.run(
                        "MERGE (p:Product {name: $name}) "
                        "WITH p "
                        "MATCH (c:Chunk {chunk_id: $chunk_id}) "
                        "MERGE (c)-[:MENTIONS]->(p)",
                        name=product, chunk_id=chunk_id,
                    )
                for topic in entities["topics"]:
                    session.run(
                        "MERGE (t:Topic {name: $name}) "
                        "WITH t "
                        "MATCH (c:Chunk {chunk_id: $chunk_id}) "
                        "MERGE (c)-[:MENTIONS]->(t)",
                        name=topic, chunk_id=chunk_id,
                    )

            # Create RELATED_TO edges between chunks that share entities
            session.run(
                "MATCH (c1:Chunk)-[:MENTIONS]->(e)<-[:MENTIONS]-(c2:Chunk) "
                "WHERE c1 <> c2 "
                "AND EXISTS { MATCH (d:Document {doc_id: $doc_id})-[:CONTAINS]->(c1) } "
                "MERGE (c1)-[:RELATED_TO]->(c2)",
                doc_id=doc_id,
            )

    async def index_document(
        self,
        doc_id: str,
        filename: str,
        title: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        await anyio.to_thread.run_sync(
            self._index_document_sync, doc_id, filename, title, chunks
        )

    def _index_conversation_sync(
        self,
        conv_id: str,
        question: str,
        answer: str,
        agent_name: str,
        product: str | None,
    ) -> None:
        with self._driver.session() as session:
            session.run(
                "MERGE (c:Conversation {conv_id: $conv_id}) "
                "SET c.question = $question, c.answer = $answer",
                conv_id=conv_id, question=question, answer=answer,
            )
            if agent_name:
                session.run(
                    "MERGE (a:Agent {name: $name}) "
                    "WITH a "
                    "MATCH (c:Conversation {conv_id: $conv_id}) "
                    "MERGE (c)-[:ANSWERED_BY]->(a)",
                    name=agent_name, conv_id=conv_id,
                )
            if product:
                session.run(
                    "MERGE (p:Product {name: $name}) "
                    "WITH p "
                    "MATCH (c:Conversation {conv_id: $conv_id}) "
                    "MERGE (c)-[:ABOUT]->(p)",
                    name=product, conv_id=conv_id,
                )

    async def index_conversation(
        self,
        conv_id: str,
        question: str,
        answer: str,
        agent_name: str,
        product: str | None,
    ) -> None:
        await anyio.to_thread.run_sync(
            self._index_conversation_sync,
            conv_id, question, answer, agent_name, product,
        )

    # ------------------------------------------------------------------ #
    #  Retrieval
    # ------------------------------------------------------------------ #
    def _search_sync(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Full-text search on chunk text + entity-based graph traversal."""
        results: list[dict[str, Any]] = []

        with self._driver.session() as session:
            # 1. Full-text search on chunk text
            try:
                records = session.run(
                    "CALL db.index.fulltext.queryNodes('chunk_text', $query) "
                    "YIELD node, score "
                    "RETURN node.chunk_id AS chunk_id, node.text_preview AS text, "
                    "       node.page AS page, node.section AS section, score "
                    "ORDER BY score DESC LIMIT $limit",
                    query=query, limit=top_k,
                )
                for record in records:
                    results.append({
                        "chunk_id": record["chunk_id"],
                        "text": record["text"],
                        "page": record["page"],
                        "section": record["section"],
                        "score": float(record["score"]),
                        "source": "fulltext",
                    })
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Graph fulltext search failed: {exc}")

            # 2. Entity-based traversal: find chunks related to query entities
            entities = _extract_entities(query)
            entity_names = entities["products"] + entities["topics"]
            if entity_names:
                try:
                    records = session.run(
                        "UNWIND $names AS name "
                        "MATCH (e {name: name})<-[:MENTIONS]-(c:Chunk) "
                        "RETURN DISTINCT c.chunk_id AS chunk_id, c.text_preview AS text, "
                        "       c.page AS page, c.section AS section, "
                        "       count(*) AS relevance "
                        "ORDER BY relevance DESC LIMIT $limit",
                        names=entity_names, limit=top_k,
                    )
                    seen = {r["chunk_id"] for r in results}
                    for record in records:
                        if record["chunk_id"] not in seen:
                            results.append({
                                "chunk_id": record["chunk_id"],
                                "text": record["text"],
                                "page": record["page"],
                                "section": record["section"],
                                "score": float(record["relevance"]) * 0.5,
                                "source": "entity_traversal",
                            })
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"Graph entity traversal failed: {exc}")

        return results[:top_k]

    async def search(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        return await anyio.to_thread.run_sync(self._search_sync, query, top_k)

    def _get_related_chunks_sync(
        self, chunk_ids: list[str], depth: int = 1
    ) -> list[dict[str, Any]]:
        """Given vector-retrieved chunk IDs, find related chunks via graph traversal."""
        results: list[dict[str, Any]] = []
        with self._driver.session() as session:
            try:
                records = session.run(
                    "UNWIND $ids AS cid "
                    "MATCH (c:Chunk {chunk_id: cid})-[:RELATED_TO*1.." + str(depth) + "]->(related:Chunk) "
                    "WHERE NOT related.chunk_id IN $ids "
                    "RETURN DISTINCT related.chunk_id AS chunk_id, "
                    "       related.text_preview AS text, "
                    "       related.page AS page, "
                    "       related.section AS section, "
                    "       count(*) AS connections "
                    "ORDER BY connections DESC LIMIT 10",
                    ids=chunk_ids,
                )
                for record in records:
                    results.append({
                        "chunk_id": record["chunk_id"],
                        "text": record["text"],
                        "page": record["page"],
                        "section": record["section"],
                        "connections": record["connections"],
                        "source": "graph_expansion",
                    })
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Graph expansion failed: {exc}")
        return results

    async def get_related_chunks(
        self, chunk_ids: list[str], depth: int = 1
    ) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        return await anyio.to_thread.run_sync(
            self._get_related_chunks_sync, chunk_ids, depth
        )

    def _delete_document_sync(self, doc_id: str) -> None:
        """Remove a document and its chunks from the graph."""
        with self._driver.session() as session:
            session.run(
                "MATCH (d:Document {doc_id: $doc_id})-[:CONTAINS]->(c:Chunk) "
                "DETACH DELETE c",
                doc_id=doc_id,
            )
            session.run(
                "MATCH (d:Document {doc_id: $doc_id}) DETACH DELETE d",
                doc_id=doc_id,
            )

    async def delete_document(self, doc_id: str) -> None:
        await anyio.to_thread.run_sync(self._delete_document_sync, doc_id)
