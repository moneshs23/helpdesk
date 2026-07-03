import { useEffect, useRef, useState } from "react";
import {
  Send,
  Copy,
  Check,
  FileText,
  Sparkles,
  Languages,
  History as HistoryIcon,
  Brain,
  Trophy,
} from "lucide-react";
import { api } from "../lib/api";
import type { ChatResponse, ConversationRecord, Suggestion } from "../lib/types";
import { Button, Card, Badge, ConfidenceBar, Spinner, EmptyState } from "../components/ui";
import { useToast } from "../context/ToastContext";

const rankColors = ["bg-brutal-yellow", "bg-brutal-blue text-white", "bg-brutal-pink"];

export default function Chat() {
  const { push } = useToast();
  const [message, setMessage] = useState("");
  const [agent, setAgent] = useState(localStorage.getItem("agent") || "");
  const [product, setProduct] = useState("");
  const [replyLang, setReplyLang] = useState<"auto" | "ja" | "en">("auto");
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<ChatResponse | null>(null);
  const [recent, setRecent] = useState<ConversationRecord[]>([]);
  const [copied, setCopied] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const loadRecent = () =>
    api.history({ limit: 12 }).then((d) => setRecent(d.conversations)).catch(() => {});

  useEffect(() => {
    loadRecent();
  }, []);

  useEffect(() => {
    localStorage.setItem("agent", agent);
  }, [agent]);

  const ask = async () => {
    if (!message.trim()) return;
    setLoading(true);
    setResp(null);
    try {
      const data = await api.chat({
        message: message.trim(),
        agent_name: agent || undefined,
        product: product || undefined,
        reply_language: replyLang,
      });
      setResp(data);
      loadRecent();
      if (!data.grounded) push("No supporting docs found for this query.", "info");
    } catch (e: any) {
      push(e?.response?.data?.detail || "Chat failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const copy = (s: Suggestion) => {
    const text = s.answer_ja ? `${s.answer_en}\n\n${s.answer_ja}` : s.answer_en;
    navigator.clipboard.writeText(text);
    setCopied(s.rank);
    push("Copied to clipboard", "success");
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div className="animate-pop-in">
      <h1 className="mb-4 font-display text-3xl font-bold">Customer Chat</h1>
      <div className="grid gap-4 lg:grid-cols-[260px_1fr_300px]">
        {/* LEFT: recent conversations */}
        <Card className="order-2 h-fit lg:order-1">
          <h2 className="mb-3 flex items-center gap-2 font-display font-bold">
            <HistoryIcon size={16} /> Recent
          </h2>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
            {recent.length === 0 && <p className="text-xs opacity-60">No conversations yet.</p>}
            {recent.map((c) => (
              <button
                key={c.id}
                onClick={() => setMessage(c.question)}
                className="w-full rounded-brutal border-2 border-brutal-ink p-2 text-left text-xs hover:bg-brutal-yellow dark:border-brutal-paper dark:hover:bg-brutal-darker"
              >
                <p className="line-clamp-2 font-bold">{c.question}</p>
                <div className="mt-1 flex items-center gap-1 opacity-70">
                  <Badge color={c.detected_language === "ja" ? "pink" : "blue"}>
                    {c.detected_language.toUpperCase()}
                  </Badge>
                  <span>{Math.round(c.confidence * 100)}%</span>
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* CENTER: chat + Top 3 */}
        <div className="order-1 space-y-4 lg:order-2">
          <Card>
            <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-3">
              <input className="brutal-input" placeholder="Agent name" value={agent} onChange={(e) => setAgent(e.target.value)} />
              <input className="brutal-input" placeholder="Product (optional)" value={product} onChange={(e) => setProduct(e.target.value)} />
              <select className="brutal-input" value={replyLang} onChange={(e) => setReplyLang(e.target.value as any)}>
                <option value="auto">Reply: Auto</option>
                <option value="en">Reply: English</option>
                <option value="ja">Reply: 日本語</option>
              </select>
            </div>
            <textarea
              ref={textareaRef}
              className="brutal-input min-h-[90px] resize-y"
              placeholder="Paste the customer's question (Japanese or English)..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask();
              }}
            />
            <div className="mt-3 flex items-center justify-between">
              <p className="text-xs opacity-60">⌘/Ctrl + Enter to send</p>
              <Button variant="blue" onClick={ask} loading={loading}>
                <Send size={16} /> Get Suggestions
              </Button>
            </div>
          </Card>

          {loading && (
            <Card>
              <Spinner label="Detecting language, retrieving docs & generating Top 3..." />
            </Card>
          )}

          {resp && (
            <>
              <Card className="!bg-brutal-purple">
                <div className="flex flex-wrap items-center gap-2 text-sm font-bold">
                  <Badge color="blue">
                    <Languages size={12} /> {resp.detected_language.toUpperCase()}
                  </Badge>
                  <Badge color={resp.grounded ? "green" : "red"}>
                    {resp.grounded ? "Grounded" : "No supporting info"}
                  </Badge>
                  <Badge color="yellow">{(resp.response_time_ms / 1000).toFixed(1)}s</Badge>
                </div>
                {resp.detected_language === "ja" && (
                  <p className="mt-2 text-sm">
                    <span className="font-bold">Translated:</span> {resp.translated_query}
                  </p>
                )}
              </Card>

              <div className="flex items-center gap-2 font-display text-xl font-bold">
                <Sparkles size={20} /> Top 3 Suggested Replies
              </div>

              {resp.suggestions.map((s) => (
                <SuggestionCard key={s.rank} s={s} onCopy={() => copy(s)} copied={copied === s.rank} />
              ))}
            </>
          )}

          {!resp && !loading && (
            <Card>
              <EmptyState
                icon={<Trophy size={40} />}
                title="Ask a question to get Top 3 grounded replies"
                hint="The assistant searches your uploaded documents and past conversations."
              />
            </Card>
          )}
        </div>

        {/* RIGHT: retrieved docs + similar */}
        <div className="order-3 space-y-4">
          <Card className="h-fit">
            <h2 className="mb-3 flex items-center gap-2 font-display font-bold">
              <FileText size={16} /> Retrieved Documents
            </h2>
            {!resp?.retrieved_documents.length && <p className="text-xs opacity-60">Nothing retrieved yet.</p>}
            <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
              {resp?.retrieved_documents.map((c) => (
                <div key={c.id} className="rounded-brutal border-2 border-brutal-ink p-2 text-xs dark:border-brutal-paper">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-bold truncate">{c.metadata.filename}</span>
                    <Badge color="blue">p{c.metadata.page}</Badge>
                  </div>
                  <ConfidenceBar value={Math.max(0, Math.min(1, c.score))} />
                  <p className="mt-1 line-clamp-3 opacity-80">{c.text}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="h-fit">
            <h2 className="mb-3 flex items-center gap-2 font-display font-bold">
              <HistoryIcon size={16} /> Similar Previous Questions
            </h2>
            {!resp?.similar_conversations.length && <p className="text-xs opacity-60">No similar questions.</p>}
            <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
              {resp?.similar_conversations.map((c, i) => (
                <div key={i} className="rounded-brutal border-2 border-brutal-ink p-2 text-xs dark:border-brutal-paper">
                  <p className="font-bold line-clamp-2">{c.question}</p>
                  <p className="mt-1 line-clamp-2 opacity-80">{c.answer}</p>
                  <div className="mt-1 flex items-center justify-between opacity-70">
                    <span>{c.agent_name}</span>
                    <Badge color="green">{Math.round(c.similarity * 100)}%</Badge>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SuggestionCard({ s, onCopy, copied }: { s: Suggestion; onCopy: () => void; copied: boolean }) {
  return (
    <Card className={`animate-slide-up ${rankColors[s.rank - 1] ?? ""}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="brutal-badge bg-white text-brutal-ink">
          <Trophy size={12} /> Suggestion {s.rank}
        </span>
        <ConfidenceBar value={s.confidence} />
      </div>
      <p className="whitespace-pre-wrap font-medium">{s.answer_en}</p>
      {s.answer_ja && (
        <p className="mt-2 whitespace-pre-wrap border-t-2 border-brutal-ink/30 pt-2 font-medium">
          {s.answer_ja}
        </p>
      )}
      {s.reasoning && (
        <p className="mt-2 flex items-start gap-1 text-xs opacity-80">
          <Brain size={14} className="mt-0.5 shrink-0" /> {s.reasoning}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {s.referenced_documents.map((d) => (
          <span key={d} className="brutal-chip bg-white">
            <FileText size={12} /> {d}
          </span>
        ))}
        {s.referenced_pages.map((p) => (
          <span key={p} className="brutal-chip bg-white">
            p{p}
          </span>
        ))}
        <button onClick={onCopy} className="brutal-btn-ghost ml-auto !py-1 !text-sm">
          {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </Card>
  );
}
