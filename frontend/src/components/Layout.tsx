import { useEffect, useState, type ReactNode } from "react";
import { Menu, Moon, Sun, Cpu, X } from "lucide-react";
import Sidebar from "./Sidebar";
import { useTheme } from "../context/ThemeContext";
import { api } from "../lib/api";

export default function Layout({ children }: { children: ReactNode }) {
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [model, setModel] = useState<string>("");
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api.settings().then((s) => setModel(s.active_model)).catch(() => setModel("unknown"));
    api
      .system()
      .then((s: any) => setOnline(s.ok))
      .catch(() => setOnline(false));
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-0 h-full animate-slide-up">
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between gap-3 border-b border-brutal-border bg-white px-4 py-3 dark:border-brutal-borderDark dark:bg-brutal-darkcard">
          <button className="brutal-btn-ghost md:hidden !px-2 !py-1" onClick={() => setOpen((o) => !o)}>
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
          <div className="flex items-center gap-2">
            <span className="brutal-badge bg-brutal-green">
              <span className={`h-2 w-2 rounded-full ${online ? "bg-brutal-ink" : "bg-brutal-red"}`} />
              {online === null ? "checking" : online ? "systems ok" : "check ollama"}
            </span>
            <span className="brutal-badge bg-brutal-blue text-white">
              <Cpu size={12} /> {model || "..."}
            </span>
          </div>
          <button className="brutal-btn-ghost !px-2 !py-1" onClick={toggle} title="Toggle theme">
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
