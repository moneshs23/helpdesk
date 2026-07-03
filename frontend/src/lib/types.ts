export type Language = "ja" | "en" | "auto" | "unknown";
export type DocumentTypeT = "pdf" | "docx" | "txt" | "csv" | "xlsx" | "md" | "unknown";
export type DocStatus = "pending" | "processing" | "ready" | "failed";
export type ConvStatus = "pending" | "answered" | "resolved";

export interface DocumentMetadata {
  id: string;
  filename: string;
  title: string;
  doc_type: DocumentTypeT;
  upload_date: string;
  size_bytes: number;
  pages: number;
  chunk_count: number;
  version: number;
  status: DocStatus;
  tags: string[];
  pinned: boolean;
  error?: string | null;
}

export interface ChunkMetadata {
  document_id: string;
  filename: string;
  title: string;
  doc_type: DocumentTypeT;
  page: number;
  section: string;
  upload_date?: string | null;
  chunk_index: number;
}

export interface RetrievedChunk {
  id: string;
  text: string;
  score: number;
  metadata: ChunkMetadata;
}

export interface SimilarConversation {
  conversation_id: string;
  question: string;
  answer: string;
  agent_name: string;
  product?: string | null;
  date: string;
  similarity: number;
}

export interface Suggestion {
  rank: number;
  answer_en: string;
  answer_ja?: string | null;
  confidence: number;
  reasoning: string;
  referenced_documents: string[];
  referenced_pages: number[];
}

export interface ChatResponse {
  conversation_id: string;
  detected_language: Language;
  original_message: string;
  translated_query: string;
  rewritten_query: string;
  suggestions: Suggestion[];
  retrieved_documents: RetrievedChunk[];
  similar_conversations: SimilarConversation[];
  grounded: boolean;
  response_time_ms: number;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  language?: Language;
  reply_language?: Language;
  customer_id?: string;
  agent_name?: string;
  product?: string;
  conversation_id?: string;
}

export interface ConversationRecord {
  id: number;
  conversation_id: string;
  customer_id?: string | null;
  agent_name?: string | null;
  product?: string | null;
  question: string;
  detected_language: Language;
  translated_query: string;
  final_reply: string;
  agent_edited_reply?: string | null;
  confidence: number;
  status: ConvStatus;
  favorite: boolean;
  pinned: boolean;
  tags: string[];
  response_time_ms: number;
  created_at: string;
}

export interface AnalyticsResponse {
  todays_queries: number;
  total_queries: number;
  avg_response_time_ms: number;
  documents_uploaded: number;
  total_chunks: number;
  most_asked_products: { product: string; count: number }[];
  top_agents: { agent_name: string; count: number }[];
  pending_queries: number;
  recent_uploads: DocumentMetadata[];
}

export interface ProductSearchResponse {
  query: string;
  grounded: boolean;
  answer: string;
  chunks: RetrievedChunk[];
}

export interface ModelInfo {
  name: string;
  size: number;
}

export interface PublicSettings {
  app_name: string;
  active_model: string;
  embedding_model: string;
  translation_engine: string;
  max_upload_mb: number;
  supported_types: string[];
}
