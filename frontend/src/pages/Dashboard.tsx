import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  MessageSquare,
  Clock,
  FileText,
  Layers,
  AlertTriangle,
  TrendingUp,
  Users,
  Upload,
  ArrowRight,
} from "lucide-react";
import { api } from "../lib/api";
import type { AnalyticsResponse } from "../lib/types";
import { Card, Spinner, Badge } from "../components/ui";

const statColors = ["bg-brutal-yellow", "bg-brutal-blue text-white", "bg-brutal-pink", "bg-brutal-green"];

export default function Dashboard() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.analytics().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Loading dashboard..." />;
  if (!data) return <p>Failed to load analytics.</p>;

  const stats = [
    { label: "Today's Queries", value: data.todays_queries, icon: MessageSquare },
    {
      label: "Avg Response Time",
      value: `${(data.avg_response_time_ms / 1000).toFixed(1)}s`,
      icon: Clock,
    },
    { label: "Documents", value: data.documents_uploaded, icon: FileText },
    { label: "Total Chunks", value: data.total_chunks, icon: Layers },
  ];

  return (
    <div className="space-y-6 animate-pop-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold">Dashboard</h1>
          <p className="opacity-70">Local AI support at a glance — fully offline.</p>
        </div>
        <Link to="/chat" className="brutal-btn-blue">
          Start assisting <ArrowRight size={16} />
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s, i) => (
          <div key={s.label} className={`brutal-card p-4 ${statColors[i]}`}>
            <div className="flex items-center justify-between">
              <s.icon size={22} />
            </div>
            <p className="mt-3 font-display text-3xl font-bold">{s.value}</p>
            <p className="text-sm font-bold opacity-80">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Most asked products */}
        <Card>
          <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-bold">
            <TrendingUp size={18} /> Most Asked Products
          </h2>
          {data.most_asked_products.length === 0 && <p className="text-sm opacity-60">No data yet.</p>}
          <ul className="space-y-2">
            {data.most_asked_products.map((p) => (
              <li key={p.product} className="flex items-center justify-between">
                <span className="font-medium">{p.product}</span>
                <Badge color="blue">{p.count}</Badge>
              </li>
            ))}
          </ul>
        </Card>

        {/* Top agents */}
        <Card>
          <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-bold">
            <Users size={18} /> Top Agents
          </h2>
          {data.top_agents.length === 0 && <p className="text-sm opacity-60">No data yet.</p>}
          <ul className="space-y-2">
            {data.top_agents.map((a) => (
              <li key={a.agent_name} className="flex items-center justify-between">
                <span className="font-medium">{a.agent_name}</span>
                <Badge color="pink">{a.count}</Badge>
              </li>
            ))}
          </ul>
        </Card>

        {/* Pending */}
        <Card className="!bg-brutal-red text-white">
          <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-bold">
            <AlertTriangle size={18} /> Pending Queries
          </h2>
          <p className="font-display text-5xl font-bold">{data.pending_queries}</p>
          <p className="mt-2 text-sm opacity-90">Ungrounded / needing agent attention.</p>
        </Card>
      </div>

      {/* Recent uploads */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold">
            <Upload size={18} /> Recent Uploads
          </h2>
          <Link to="/upload" className="brutal-btn-yellow !py-1 !text-sm">
            Upload
          </Link>
        </div>
        {data.recent_uploads.length === 0 && <p className="text-sm opacity-60">No documents uploaded yet.</p>}
        <div className="grid gap-2 md:grid-cols-2">
          {data.recent_uploads.map((d) => (
            <div key={d.id} className="flex items-center justify-between rounded-brutal border-2 border-brutal-ink px-3 py-2 dark:border-brutal-paper">
              <div className="min-w-0">
                <p className="truncate font-bold">{d.title}</p>
                <p className="truncate text-xs opacity-60">{d.filename}</p>
              </div>
              <Badge color={d.status === "ready" ? "green" : d.status === "failed" ? "red" : "yellow"}>
                {d.chunk_count} chunks
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
