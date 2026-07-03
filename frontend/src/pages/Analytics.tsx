import { useEffect, useState } from "react";
import { BarChart3, Clock, MessageSquare, FileText, Layers, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import type { AnalyticsResponse } from "../lib/types";
import { Card, Spinner, Badge } from "../components/ui";

function Bars({
  data,
  color,
}: {
  data: { label: string; value: number }[];
  color: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (data.length === 0) return <p className="text-sm opacity-60">No data yet.</p>;
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-2">
          <span className="w-28 truncate text-sm font-bold">{d.label}</span>
          <div className="h-6 flex-1 border-2 border-brutal-ink dark:border-brutal-paper rounded-brutal overflow-hidden bg-white dark:bg-brutal-darker">
            <div className={`h-full ${color}`} style={{ width: `${(d.value / max) * 100}%` }} />
          </div>
          <span className="w-8 text-right text-sm font-bold">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.analytics().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Crunching numbers..." />;
  if (!data) return <p>Failed to load analytics.</p>;

  const cards = [
    { label: "Total Queries", value: data.total_queries, icon: MessageSquare, c: "bg-brutal-yellow" },
    { label: "Today", value: data.todays_queries, icon: BarChart3, c: "bg-brutal-blue text-white" },
    { label: "Avg Time", value: `${(data.avg_response_time_ms / 1000).toFixed(1)}s`, icon: Clock, c: "bg-brutal-pink" },
    { label: "Documents", value: data.documents_uploaded, icon: FileText, c: "bg-brutal-green" },
    { label: "Chunks", value: data.total_chunks, icon: Layers, c: "bg-brutal-purple" },
    { label: "Pending", value: data.pending_queries, icon: AlertTriangle, c: "bg-brutal-red text-white" },
  ];

  return (
    <div className="space-y-6 animate-pop-in">
      <h1 className="flex items-center gap-2 font-display text-3xl font-bold">
        <BarChart3 size={28} /> Analytics
      </h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {cards.map((s) => (
          <div key={s.label} className={`brutal-card p-3 ${s.c}`}>
            <s.icon size={18} />
            <p className="mt-2 font-display text-2xl font-bold">{s.value}</p>
            <p className="text-xs font-bold opacity-80">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-display text-lg font-bold">Most Asked Products</h2>
          <Bars
            data={data.most_asked_products.map((p) => ({ label: p.product, value: p.count }))}
            color="bg-brutal-blue"
          />
        </Card>
        <Card>
          <h2 className="mb-3 font-display text-lg font-bold">Top Agents</h2>
          <Bars
            data={data.top_agents.map((a) => ({ label: a.agent_name, value: a.count }))}
            color="bg-brutal-pink"
          />
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-display text-lg font-bold">Recent Uploads</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {data.recent_uploads.map((d) => (
            <div key={d.id} className="flex items-center justify-between rounded-brutal border-2 border-brutal-ink px-3 py-2 dark:border-brutal-paper">
              <span className="truncate font-bold">{d.title}</span>
              <Badge color="green">{d.chunk_count} chunks</Badge>
            </div>
          ))}
          {data.recent_uploads.length === 0 && <p className="text-sm opacity-60">No uploads yet.</p>}
        </div>
      </Card>
    </div>
  );
}
