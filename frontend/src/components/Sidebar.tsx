import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Upload,
  History,
  BarChart3,
  Settings,
  Headphones,
  MessageCircle,
  Inbox,
} from "lucide-react";
import clsx from "clsx";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/customer", label: "Customer View", icon: MessageCircle },
  { to: "/agent", label: "Agent Console", icon: Inbox },
  { to: "/upload", label: "Upload Documents", icon: Upload },
  { to: "/history", label: "Conversation History", icon: History },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <aside className="flex h-full w-64 flex-col gap-4 border-r-[3px] border-brutal-ink bg-brutal-yellow p-4 dark:border-brutal-paper dark:bg-brutal-darkcard">
      <div className="brutal-card flex items-center gap-2 bg-brutal-pink p-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-brutal border-2 border-brutal-ink bg-white">
          <Headphones size={20} />
        </div>
        <div className="leading-tight">
          <p className="font-display text-sm font-bold">AI SUPPORT</p>
          <p className="text-[10px] font-bold uppercase tracking-wide">Assistant</p>
        </div>
      </div>

      <nav className="flex flex-col gap-2">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-brutal border-[3px] border-brutal-ink px-3 py-2 text-sm font-bold transition-all dark:border-brutal-paper",
                isActive
                  ? "bg-brutal-blue text-white shadow-brutal dark:shadow-brutal-white"
                  : "bg-white hover:-translate-y-[1px] hover:shadow-brutal dark:bg-brutal-darker dark:text-brutal-paper dark:hover:shadow-brutal-white"
              )
            }
          >
            <Icon size={18} /> {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto brutal-card bg-white p-3 text-[11px] font-bold dark:bg-brutal-darker">
        <p className="mb-1 flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-brutal-green inline-block" />
          100% Offline
        </p>
        <p className="opacity-70">Gemma 3 · Local RAG · No Cloud</p>
      </div>
    </aside>
  );
}
