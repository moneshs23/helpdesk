"""Pydantic request/response schemas (the typed API contract)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.models.enums import (
    ConversationStatus,
    DocumentStatus,
    DocumentType,
    Language,
)


# ============================================================
#  Documents
# ============================================================
class DocumentMetadata(BaseModel):
    id: str
    filename: str
    title: str
    doc_type: DocumentType
    upload_date: datetime
    size_bytes: int = 0
    pages: int = 0
    chunk_count: int = 0
    version: int = 1
    status: DocumentStatus = DocumentStatus.READY
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    error: Optional[str] = None


class UploadResponse(BaseModel):
    document: DocumentMetadata
    message: str = "Document ingested successfully."


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata]
    total: int


class DocumentVersionInfo(BaseModel):
    version: int
    upload_date: datetime
    size_bytes: int
    chunk_count: int
    note: Optional[str] = None


# ============================================================
#  Chunks / retrieval
# ============================================================
class ChunkMetadata(BaseModel):
    document_id: str
    filename: str
    title: str
    doc_type: DocumentType
    page: int = 0
    section: str = ""
    upload_date: Optional[datetime] = None
    chunk_index: int = 0


class RetrievedChunk(BaseModel):
    id: str
    text: str
    score: float
    metadata: ChunkMetadata


class SimilarConversation(BaseModel):
    conversation_id: str
    question: str
    answer: str
    agent_name: str
    product: Optional[str] = None
    date: datetime
    similarity: float


# ============================================================
#  Chat / suggestions
# ============================================================
class Suggestion(BaseModel):
    rank: int
    answer_en: str
    answer_ja: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    referenced_documents: list[str] = Field(default_factory=list)
    referenced_pages: list[int] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: Language = Language.AUTO
    reply_language: Language = Language.AUTO
    customer_id: Optional[str] = None
    agent_name: Optional[str] = None
    product: Optional[str] = None
    conversation_id: Optional[str] = None
    top_k_docs: Optional[int] = None
    top_k_chats: Optional[int] = None
    persist: bool = True  # set False when only assisting an existing ticket


class ChatResponse(BaseModel):
    conversation_id: str
    detected_language: Language
    original_message: str
    translated_query: str
    rewritten_query: str
    suggestions: list[Suggestion]
    retrieved_documents: list[RetrievedChunk]
    similar_conversations: list[SimilarConversation]
    grounded: bool
    response_time_ms: int
    created_at: datetime


# ============================================================
#  History
# ============================================================
class ConversationRecord(BaseModel):
    id: int
    conversation_id: str
    customer_id: Optional[str] = None
    agent_name: Optional[str] = None
    product: Optional[str] = None
    question: str
    detected_language: Language
    translated_query: str
    final_reply: str
    agent_edited_reply: Optional[str] = None
    confidence: float = 0.0
    status: ConversationStatus = ConversationStatus.ANSWERED
    favorite: bool = False
    pinned: bool = False
    tags: list[str] = Field(default_factory=list)
    response_time_ms: int = 0
    created_at: datetime


class HistoryResponse(BaseModel):
    conversations: list[ConversationRecord]
    total: int


class UpdateConversationRequest(BaseModel):
    agent_edited_reply: Optional[str] = None
    favorite: Optional[bool] = None
    pinned: Optional[bool] = None
    status: Optional[ConversationStatus] = None
    tags: Optional[list[str]] = None


# ============================================================
#  Tickets (two-sided: customer <-> agent)
# ============================================================
class CustomerAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    customer_id: Optional[str] = None
    product: Optional[str] = None


class TicketRecord(BaseModel):
    id: int
    conversation_id: str
    customer_id: Optional[str] = None
    agent_name: Optional[str] = None
    product: Optional[str] = None
    question: str
    detected_language: Language
    translated_query: str
    final_reply: str
    customer_reply: str = ""
    confidence: float = 0.0
    status: ConversationStatus = ConversationStatus.PENDING
    response_time_ms: int = 0
    created_at: datetime
    answered_at: Optional[datetime] = None


class TicketListResponse(BaseModel):
    tickets: list[TicketRecord]
    total: int


class TicketReplyRequest(BaseModel):
    reply: str = Field(min_length=1)
    agent_name: Optional[str] = None
    confidence: Optional[float] = None
    resolved: bool = False


class CustomerStatusResponse(BaseModel):
    conversation_id: str
    question: str
    status: ConversationStatus
    reply: str = ""            # in the customer's language
    language: Language = Language.EN
    agent_name: Optional[str] = None
    answered_at: Optional[datetime] = None


# ============================================================
#  Translation
# ============================================================
class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    source: Language = Language.AUTO
    target: Language = Language.EN


class TranslateResponse(BaseModel):
    source_language: Language
    target_language: Language
    original: str
    translated: str
    engine: str


# ============================================================
#  Products / search
# ============================================================
class ProductSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    product: Optional[str] = None
    top_k: int = 6


class ProductSearchResponse(BaseModel):
    query: str
    grounded: bool
    answer: str
    chunks: list[RetrievedChunk]


class SearchRequest(BaseModel):
    query: str = ""
    mode: str = "hybrid"  # hybrid | semantic | keyword | metadata
    product: Optional[str] = None
    doc_type: Optional[DocumentType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    top_k: int = 10


# ============================================================
#  Analytics
# ============================================================
class ProductCount(BaseModel):
    product: str
    count: int


class AgentCount(BaseModel):
    agent_name: str
    count: int


class AnalyticsResponse(BaseModel):
    todays_queries: int
    total_queries: int
    avg_response_time_ms: float
    documents_uploaded: int
    total_chunks: int
    most_asked_products: list[ProductCount]
    top_agents: list[AgentCount]
    pending_queries: int
    recent_uploads: list[DocumentMetadata]


# ============================================================
#  Generic
# ============================================================
class MessageResponse(BaseModel):
    message: str
    detail: Optional[Any] = None
