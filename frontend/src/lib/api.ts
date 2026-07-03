import axios from "axios";
import type {
  AnalyticsResponse,
  ChatRequest,
  ChatResponse,
  ConversationRecord,
  DocumentMetadata,
  ModelInfo,
  ProductSearchResponse,
  PublicSettings,
  SimilarConversation,
} from "./types";

const client = axios.create({
  baseURL: "/api",
  timeout: 180_000, // LLM generation on M1 can take a while
});

export const api = {
  // ---- system ----
  health: () => client.get<{ status: string }>("/health").then((r) => r.data),
  system: () => client.get("/system").then((r) => r.data),
  settings: () => client.get<PublicSettings>("/settings").then((r) => r.data),
  models: () => client.get<ModelInfo[]>("/models").then((r) => r.data),
  selectModel: (model: string) =>
    client.post("/models/select", { model }).then((r) => r.data),

  // ---- chat ----
  chat: (body: ChatRequest) =>
    client.post<ChatResponse>("/chat", body).then((r) => r.data),

  // ---- documents ----
  upload: (form: FormData) =>
    client
      .post<{ document: DocumentMetadata; message: string }>("/upload", form)
      .then((r) => r.data),
  listDocuments: (params?: { product?: string; query?: string }) =>
    client
      .get<{ documents: DocumentMetadata[]; total: number }>("/documents", { params })
      .then((r) => r.data),
  getDocument: (id: string) =>
    client.get<DocumentMetadata>(`/documents/${id}`).then((r) => r.data),
  documentVersions: (id: string) =>
    client.get(`/documents/${id}/versions`).then((r) => r.data),
  updateDocument: (id: string, body: Partial<DocumentMetadata>) =>
    client.patch<DocumentMetadata>(`/documents/${id}`, body).then((r) => r.data),
  replaceDocument: (id: string, form: FormData) =>
    client.put(`/documents/${id}/replace`, form).then((r) => r.data),
  deleteDocument: (id: string) =>
    client.delete(`/documents/${id}`).then((r) => r.data),
  previewUrl: (id: string) => `/api/documents/${id}/preview`,

  // ---- history ----
  history: (params?: {
    query?: string;
    product?: string;
    agent_name?: string;
    favorite?: boolean;
    limit?: number;
    offset?: number;
  }) =>
    client
      .get<{ conversations: ConversationRecord[]; total: number }>("/history", { params })
      .then((r) => r.data),
  searchHistory: (query: string, top_k = 5) =>
    client
      .get<SimilarConversation[]>("/history/search", { params: { query, top_k } })
      .then((r) => r.data),
  updateConversation: (id: number, body: Partial<ConversationRecord>) =>
    client.patch<ConversationRecord>(`/history/${id}`, body).then((r) => r.data),
  deleteConversation: (id: number) =>
    client.delete(`/history/${id}`).then((r) => r.data),
  exportCsvUrl: "/api/history/export.csv",
  exportJsonUrl: "/api/history/export.json",

  // ---- translate ----
  translate: (text: string, target: "ja" | "en", source: "ja" | "en" | "auto" = "auto") =>
    client.post("/translate", { text, target, source }).then((r) => r.data),

  // ---- products ----
  products: (query: string, product?: string) =>
    client
      .post<ProductSearchResponse>("/products", { query, product })
      .then((r) => r.data),

  // ---- analytics ----
  analytics: () => client.get<AnalyticsResponse>("/analytics").then((r) => r.data),
};
