import { useState } from "react";
import { Package, Search, FileText, ShieldCheck, AlertCircle } from "lucide-react";
import { api } from "../lib/api";
import type { ProductSearchResponse } from "../lib/types";
import { Button, Card, Badge, Spinner, ConfidenceBar } from "../components/ui";
import { useToast } from "../context/ToastContext";

const intents = [
  "Price",
  "Warranty",
  "Spare Part",
  "Maintenance",
  "Installation",
  "Safety",
  "Repair",
  "Return Policy",
];

export default function Products() {
  const { push } = useToast();
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState("");
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<ProductSearchResponse | null>(null);

  const run = async (q?: string) => {
    const question = q ?? query;
    if (!question.trim()) return;
    setQuery(question);
    setLoading(true);
    setResp(null);
    try {
      const data = await api.products(question, product || undefined);
      setResp(data);
    } catch (e: any) {
      push(e?.response?.data?.detail || "Search failed", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-pop-in">
      <div>
        <h1 className="flex items-center gap-2 font-display text-3xl font-bold">
          <Package size={28} /> Product Information
        </h1>
        <p className="opacity-70">Grounded answers on price, warranty, parts, safety & more.</p>
      </div>

      <Card>
        <div className="mb-3 flex flex-wrap gap-2">
          {intents.map((i) => (
            <button key={i} className="brutal-chip bg-brutal-blue text-white" onClick={() => run(`What is the ${i.toLowerCase()}?`)}>
              {i}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <input className="brutal-input flex-1" placeholder="Ask about a product..." value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} />
          <input className="brutal-input md:!w-56" placeholder="Product filter (optional)" value={product} onChange={(e) => setProduct(e.target.value)} />
          <Button variant="blue" onClick={() => run()} loading={loading}>
            <Search size={16} /> Search
          </Button>
        </div>
      </Card>

      {loading && (
        <Card>
          <Spinner label="Searching documents..." />
        </Card>
      )}

      {resp && (
        <Card className={resp.grounded ? "!bg-brutal-green" : "!bg-brutal-red text-white"}>
          <div className="mb-2 flex items-center gap-2 font-display font-bold">
            {resp.grounded ? <ShieldCheck size={18} /> : <AlertCircle size={18} />}
            {resp.grounded ? "Answer (grounded in documents)" : "No supporting information"}
          </div>
          <p className="whitespace-pre-wrap font-medium">{resp.answer}</p>
        </Card>
      )}

      {resp && resp.chunks.length > 0 && (
        <Card>
          <h2 className="mb-3 flex items-center gap-2 font-display font-bold">
            <FileText size={16} /> Source Chunks
          </h2>
          <div className="grid gap-2 md:grid-cols-2">
            {resp.chunks.map((c) => (
              <div key={c.id} className="rounded-brutal border-2 border-brutal-ink p-2 text-xs dark:border-brutal-paper">
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-bold truncate">{c.metadata.filename}</span>
                  <Badge color="blue">p{c.metadata.page}</Badge>
                </div>
                <ConfidenceBar value={Math.max(0, Math.min(1, c.score))} />
                <p className="mt-1 line-clamp-4 opacity-80">{c.text}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
