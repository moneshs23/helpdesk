import { useEffect, useState } from "react";
import { Settings as Cog, Cpu, Sun, Moon, Wifi, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { api } from "../lib/api";
import type { ModelInfo, PublicSettings } from "../lib/types";
import { Button, Card, Badge, Spinner } from "../components/ui";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";

export default function SettingsPage() {
  const { theme, toggle } = useTheme();
  const { push } = useToast();
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState("");
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    Promise.all([api.settings(), api.models().catch(() => []), api.system().catch(() => null)])
      .then(([s, m, h]) => {
        setSettings(s);
        setSelected(s.active_model);
        setModels(m);
        setHealth(h);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const applyModel = async () => {
    await api.selectModel(selected);
    push(`Active model set to ${selected}`, "success");
    load();
  };

  if (loading) return <Spinner label="Loading settings..." />;

  return (
    <div className="space-y-6 animate-pop-in max-w-3xl">
      <h1 className="flex items-center gap-2 font-display text-3xl font-bold">
        <Cog size={28} /> Settings
      </h1>

      {/* Model */}
      <Card>
        <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-bold">
          <Cpu size={18} /> Language Model (Ollama)
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <select className="brutal-input flex-1" value={selected} onChange={(e) => setSelected(e.target.value)}>
            {models.length === 0 && <option value={settings?.active_model}>{settings?.active_model}</option>}
            {models.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name} ({(m.size / 1e9).toFixed(1)} GB)
              </option>
            ))}
          </select>
          <Button variant="blue" onClick={applyModel}>
            Apply
          </Button>
          <Button variant="ghost" onClick={load}>
            <RefreshCw size={16} />
          </Button>
        </div>
        <p className="mt-2 text-xs opacity-60">
          Default is <b>gemma3:4b</b>. Switching applies immediately to new chats.
        </p>
      </Card>

      {/* System info */}
      <Card>
        <h2 className="mb-3 font-display text-lg font-bold">System</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          <Info label="Embedding model" value={settings?.embedding_model} />
          <Info label="Translation engine" value={settings?.translation_engine} />
          <Info label="Max upload" value={`${settings?.max_upload_mb} MB`} />
          <Info label="Supported types" value={settings?.supported_types.join(", ")} />
        </div>
      </Card>

      {/* Health */}
      <Card>
        <h2 className="mb-3 font-display text-lg font-bold">Health Checks</h2>
        <div className="space-y-2">
          {health?.components?.map((c: any) => (
            <div key={c.name} className="flex items-center justify-between rounded-brutal border border-brutal-border px-3 py-2 dark:border-brutal-borderDark">
              <span className="font-bold">{c.name}</span>
              <span className="flex items-center gap-1 text-sm">
                {c.ok ? <CheckCircle2 size={16} className="text-green-600" /> : <XCircle size={16} className="text-red-600" />}
                {c.detail}
              </span>
            </div>
          ))}
          {!health && <p className="text-sm opacity-60">Ollama not reachable.</p>}
        </div>
      </Card>

      {/* Appearance + LAN */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-display text-lg font-bold">Appearance</h2>
          <Button variant={theme === "dark" ? "pink" : "yellow"} onClick={toggle}>
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </Button>
        </Card>
        <Card>
          <h2 className="mb-2 flex items-center gap-2 font-display text-lg font-bold">
            <Wifi size={18} /> LAN Access
          </h2>
          <p className="text-sm opacity-80">
            Reachable at <Badge color="blue">{window.location.host}</Badge> on your network.
          </p>
          <p className="mt-1 text-xs opacity-60">Run <code>make lan</code> to print device URLs.</p>
        </Card>
      </div>

      <div className="brutal-card bg-brutal-yellow p-3 text-center text-sm font-bold">
        🔒 100% offline · No Google · No OpenAI · No cloud services
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string }) {
  return (
    <div className="rounded-brutal border border-brutal-border px-3 py-2 dark:border-brutal-borderDark">
      <p className="text-xs font-bold opacity-60">{label}</p>
      <p className="font-medium">{value ?? "—"}</p>
    </div>
  );
}
