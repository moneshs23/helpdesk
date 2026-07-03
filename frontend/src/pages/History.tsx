import { useCallback, useEffect, useState } from "react";
import {
  Search,
  Star,
  Trash2,
  Download,
  Pencil,
  Save,
  X,
  FileDown,
} from "lucide-react";
import { api } from "../lib/api";
import type { ConversationRecord } from "../lib/types";
import { Button, Card, Badge, Spinner, EmptyState, ConfidenceBar } from "../components/ui";
import { useToast } from "../context/ToastContext";

export default function HistoryPage() {
  const { push } = useToast();
  const [items, setItems] = useState<ConversationRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [favOnly, setFavOnly] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api
      .history({ query: query || undefined, favorite: favOnly || undefined, limit: 100 })
      .then((d) => {
        setItems(d.conversations);
        setTotal(d.total);
      })
      .finally(() => setLoading(false));
  }, [query, favOnly]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const toggleFav = async (c: ConversationRecord) => {
    await api.updateConversation(c.id, { favorite: !c.favorite });
    load();
  };

  const saveEdit = async (c: ConversationRecord) => {
    await api.updateConversation(c.id, { agent_edited_reply: draft });
    setEditing(null);
    push("Reply saved", "success");
    load();
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this conversation?")) return;
    await api.deleteConversation(id);
    load();
  };

  return (
    <div className="space-y-6 animate-pop-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold">Conversation History</h1>
          <p className="opacity-70">{total} stored conversations · searchable memory</p>
        </div>
        <div className="flex items-center gap-2">
          <a className="brutal-btn-yellow !py-1 !text-sm" href={api.exportCsvUrl}>
            <FileDown size={14} /> CSV
          </a>
          <a className="brutal-btn-blue !py-1 !text-sm" href={api.exportJsonUrl}>
            <Download size={14} /> JSON
          </a>
        </div>
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-1 items-center gap-1 brutal-input">
            <Search size={16} />
            <input
              className="w-full bg-transparent outline-none"
              placeholder="Search questions & replies..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <Button variant={favOnly ? "pink" : "ghost"} onClick={() => setFavOnly((f) => !f)}>
            <Star size={16} /> Favorites
          </Button>
        </div>
      </Card>

      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState icon={<Search size={40} />} title="No conversations found" />
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((c) => (
            <Card key={c.id} className="animate-slide-up">
              <div className="flex flex-wrap items-center gap-2">
                <Badge color={c.detected_language === "ja" ? "pink" : "blue"}>
                  {c.detected_language.toUpperCase()}
                </Badge>
                {c.product && <Badge color="purple">{c.product}</Badge>}
                {c.agent_name && <Badge color="yellow">{c.agent_name}</Badge>}
                <Badge color={c.status === "answered" ? "green" : c.status === "pending" ? "red" : "blue"}>
                  {c.status}
                </Badge>
                <span className="ml-auto text-xs opacity-60">
                  {new Date(c.created_at).toLocaleString()}
                </span>
              </div>

              <p className="mt-2 font-bold">{c.question}</p>
              {c.translated_query && c.detected_language === "ja" && (
                <p className="text-sm opacity-70">↳ {c.translated_query}</p>
              )}

              <div className="mt-2 rounded-brutal border-2 border-brutal-ink bg-brutal-paper p-2 dark:border-brutal-paper dark:bg-brutal-darker">
                {editing === c.id ? (
                  <div className="space-y-2">
                    <textarea className="brutal-input min-h-[80px]" value={draft} onChange={(e) => setDraft(e.target.value)} />
                    <div className="flex gap-2">
                      <Button variant="blue" className="!py-1 !text-sm" onClick={() => saveEdit(c)}>
                        <Save size={14} /> Save
                      </Button>
                      <Button variant="ghost" className="!py-1 !text-sm" onClick={() => setEditing(null)}>
                        <X size={14} /> Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap text-sm">{c.agent_edited_reply || c.final_reply}</p>
                )}
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <ConfidenceBar value={c.confidence} />
                <span className="text-xs opacity-60">{(c.response_time_ms / 1000).toFixed(1)}s</span>
                <div className="ml-auto flex items-center gap-1">
                  <button
                    className="brutal-btn-ghost !px-2 !py-1"
                    onClick={() => {
                      setEditing(c.id);
                      setDraft(c.agent_edited_reply || c.final_reply);
                    }}
                    title="Edit reply"
                  >
                    <Pencil size={14} />
                  </button>
                  <button className={`!px-2 !py-1 ${c.favorite ? "brutal-btn-pink" : "brutal-btn-ghost"}`} onClick={() => toggleFav(c)} title="Favorite">
                    <Star size={14} />
                  </button>
                  <button className="brutal-btn-pink !px-2 !py-1" onClick={() => remove(c.id)} title="Delete">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
