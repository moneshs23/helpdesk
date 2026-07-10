import { useCallback, useEffect, useState } from "react";
import {
  Inbox,
  Sparkles,
  Send,
  FileText,
  Brain,
  Trophy,
  Languages,
  RefreshCw,
  CheckCircle2,
  History as HistoryIcon,
  Calendar,
  User,
} from "lucide-react";
import { api } from "../lib/api";
import type { ChatResponse, Suggestion, TicketRecord } from "../lib/types";
import { Button, Card, Badge, ConfidenceBar, Spinner, EmptyState } from "../components/ui";
import { useToast } from "../context/ToastContext";

export default function Agent() {
  const { push } = useToast();
  const [agent, setAgent] = useState(localStorage.getItem("agent") || "");
  const [tickets, setTickets] = useState<TicketRecord[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<TicketRecord | null>(null);
  const [assist, setAssist] = useState<ChatResponse | null>(null);
  const [assisting, setAssisting] = useState(false);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);

  const loadTickets = useCallback(() => {
    api
      .listTickets(showAll ? "all" : "pending")
      .then((d) => setTickets(d.tickets))
      .catch(() => {});
  }, [showAll]);

  useEffect(() => {
    loadTickets();
    const id = setInterval(loadTickets, 5000);
    return () => clearInterval(id);
  }, [loadTickets]);

  useEffect(() => {
    localStorage.setItem("agent", agent);
  }, [agent]);

  const openTicket = (t: TicketRecord) => {
    setSelected(t);
    setAssist(null);
    setReply(t.final_reply || "");
  };

  const generate = async () => {
    if (!selected) return;
    setAssisting(true);
    setAssist(null);
    try {
      const data = await api.chat({
        message: selected.question,
        conversation_id: selected.conversation_id,
        product: selected.product || undefined,
        reply_language: "en",
        persist: false,
      });
      setAssist(data);
      if (data.suggestions[0]) setReply(data.suggestions[0].answer_en);
      if (!data.grounded) push("No supporting docs found — answer manually.", "info");
    } catch (e: any) {
      push(e?.response?.data?.detail || "Failed to generate", "error");
    } finally {
      setAssisting(false);
    }
  };

  const send = async (resolved: boolean) => {
    if (!selected || !reply.trim()) return;
    setSending(true);
    try {
      const conf = assist?.suggestions?.[0]?.confidence;
      await api.ticketReply(selected.id, reply.trim(), agent || undefined, conf, resolved);
      push("Reply sent to customer", "success");
      setSelected(null);
      setAssist(null);
      setReply("");
      loadTickets();
    } catch (e: any) {
      push(e?.response?.data?.detail || "Failed to send", "error");
    } finally {
      setSending(false);
    }
  };

  const pendingCount = tickets.filter((t) => t.status === "pending").length;

  return (
    <div className="animate-pop-in">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-2 font-display text-3xl font-bold">
            <Inbox size={28} /> Agent Console
          </h1>
          <p className="opacity-70">Answer customer tickets with AI-assisted Top-3 replies.</p>
        </div>
        <input className="brutal-input !w-44" placeholder="Your agent name" value={agent} onChange={(e) => setAgent(e.target.value)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[300px_1fr_300px]">
        {/* LEFT: ticket inbox */}
        <Card className="h-fit">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-display font-bold">
              <Inbox size={16} /> Tickets
              <Badge color="red">{pendingCount}</Badge>
            </h2>
            <div className="flex gap-1">
              <button className={`!px-2 !py-1 text-xs ${showAll ? "brutal-btn-ghost" : "brutal-btn-blue"}`} onClick={() => setShowAll(false)}>
                Pending
              </button>
              <button className={`!px-2 !py-1 text-xs ${showAll ? "brutal-btn-blue" : "brutal-btn-ghost"}`} onClick={() => setShowAll(true)}>
                All
              </button>
              <button className="brutal-btn-ghost !px-2 !py-1" onClick={loadTickets}>
                <RefreshCw size={12} />
              </button>
            </div>
          </div>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
            {tickets.length === 0 && <p className="text-xs opacity-60">No tickets.</p>}
            {tickets.map((t) => (
              <button
                key={t.id}
                onClick={() => openTicket(t)}
                className={`w-full rounded-brutal border border-brutal-border p-2 text-left text-xs dark:border-brutal-borderDark ${
                  selected?.id === t.id ? "bg-brutal-yellow" : "hover:bg-brutal-yellow/40"
                }`}
              >
                <div className="mb-1 flex items-center gap-1">
                  <Badge color={t.detected_language === "ja" ? "pink" : "blue"}>{t.detected_language.toUpperCase()}</Badge>
                  <Badge color={t.status === "pending" ? "red" : "green"}>{t.status}</Badge>
                  {t.customer_id && <span className="opacity-60">{t.customer_id}</span>}
                </div>
                <p className="line-clamp-2 font-bold">{t.question}</p>
                <p className="mt-1 opacity-50">{new Date(t.created_at).toLocaleTimeString()}</p>
              </button>
            ))}
          </div>
        </Card>

        {/* CENTER: selected ticket + AI + compose */}
        <div className="space-y-4">
          {!selected ? (
            <Card>
              <EmptyState icon={<Inbox size={40} />} title="Select a ticket to answer" hint="Pending customer questions appear on the left." />
            </Card>
          ) : (
            <>
              <Card className="!bg-brutal-purple">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge color="blue"><Languages size={12} /> {selected.detected_language.toUpperCase()}</Badge>
                  {selected.product && <Badge color="yellow">{selected.product}</Badge>}
                  {selected.customer_id && <Badge color="pink">{selected.customer_id}</Badge>}
                </div>
                <p className="font-bold">{selected.question}</p>
                {selected.detected_language === "ja" && (
                  <p className="mt-1 text-sm opacity-80">↳ {selected.translated_query}</p>
                )}
              </Card>

              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 font-display text-lg font-bold">
                  <Sparkles size={18} /> AI Suggestions
                </h2>
                <Button variant="blue" onClick={generate} loading={assisting}>
                  <Brain size={16} /> Generate Top 3
                </Button>
              </div>

              {assisting && <Card><Spinner label="Searching docs & generating..." /></Card>}

              {assist?.suggestions.map((s) => (
                <SuggestionCard key={s.rank} s={s} onUse={() => setReply(s.answer_en)} />
              ))}

              {/* Compose */}
              <Card>
                <h2 className="mb-2 flex items-center gap-2 font-display font-bold">
                  <Send size={16} /> Reply to customer
                </h2>
                <textarea
                  className="brutal-input min-h-[110px]"
                  placeholder="Write or edit the reply. It will be translated to the customer's language automatically."
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs opacity-60">
                    {selected.detected_language === "ja" ? "Auto-translated to 日本語 for the customer." : "Sent as English."}
                  </p>
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => send(false)} loading={sending}>
                      <Send size={16} /> Send
                    </Button>
                    <Button variant="pink" onClick={() => send(true)} loading={sending}>
                      <CheckCircle2 size={16} /> Send & Resolve
                    </Button>
                  </div>
                </div>
              </Card>
            </>
          )}
        </div>

        {/* RIGHT: sources */}
        <div className="space-y-4">
          <Card className="h-fit">
            <h2 className="mb-3 flex items-center gap-2 font-display font-bold">
              <FileText size={16} /> Retrieved Documents
            </h2>
            {!assist?.retrieved_documents.length && <p className="text-xs opacity-60">Generate suggestions to see sources.</p>}
            <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
              {assist?.retrieved_documents.map((c) => (
                <div key={c.id} className="rounded-brutal border border-brutal-border p-2 text-xs dark:border-brutal-borderDark">
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
              <HistoryIcon size={16} /> Similar Past Answers
            </h2>
            {!assist?.similar_conversations.length && <p className="text-xs opacity-60">None yet.</p>}
            <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
              {assist?.similar_conversations.map((c, i) => (
                <div key={i} className="rounded-brutal border border-brutal-border p-2 text-xs dark:border-brutal-borderDark">
                  <p className="font-bold line-clamp-2">{c.question}</p>
                  <p className="mt-1 line-clamp-2 opacity-80">{c.answer}</p>
                  <div className="mt-1 flex items-center gap-2 opacity-70 flex-wrap">
                    <span className="flex items-center gap-1">
                      <User size={10} /> {c.agent_name}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar size={10} /> {new Date(c.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
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

function SuggestionCard({ s, onUse }: { s: Suggestion; onUse: () => void }) {
  const colors = ["bg-brutal-yellow", "bg-brutal-blue text-white", "bg-brutal-pink"];
  return (
    <Card className={`animate-slide-up ${colors[s.rank - 1] ?? ""}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="brutal-badge bg-white text-brutal-ink"><Trophy size={12} /> Suggestion {s.rank}</span>
        <ConfidenceBar value={s.confidence} />
      </div>
      <p className="whitespace-pre-wrap font-medium">{s.answer_en}</p>
      {s.reasoning && (
        <p className="mt-2 flex items-start gap-1 text-xs opacity-80">
          <Brain size={14} className="mt-0.5 shrink-0" /> {s.reasoning}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {s.referenced_documents.map((d) => (
          <span key={d} className="brutal-chip bg-white"><FileText size={12} /> {d}</span>
        ))}
        {s.referenced_pages.map((p) => (
          <span key={p} className="brutal-chip bg-white">p{p}</span>
        ))}
        <button onClick={onUse} className="brutal-btn-ghost ml-auto !py-1 !text-sm">
          Use this
        </button>
      </div>
    </Card>
  );
}
