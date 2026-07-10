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
    <aside className="flex h-full w-64 flex-col gap-4 border-r border-brutal-border bg-white p-4 dark:border-brutal-borderDark dark:bg-brutal-darkcard">
      <div className="flex items-center gap-2.5 px-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-brutal bg-brutal-blue text-white">
          <Headphones size={18} />
        </div>
        <div className="leading-tight">
          <p className="font-display text-sm font-semibold">AI Support</p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">Assistant</p>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-brutal px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brutal-blue text-white shadow-brutal-sm"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              )
            }
          >
            <Icon size={18} /> {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto rounded-brutal border border-brutal-border bg-slate-50 p-3 text-[11px] font-medium dark:border-brutal-borderDark dark:bg-brutal-darker">
        <p className="mb-1 flex items-center gap-1.5 text-slate-700 dark:text-slate-200">
          <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block" />
          100% Offline
        </p>
        <p className="text-slate-500 dark:text-slate-400">Gemma 3 · Local RAG · No Cloud</p>
      </div>
    </aside>
  );
}
