import clsx from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";

type Variant = "yellow" | "blue" | "pink" | "ghost";

export function Button({
  variant = "ghost",
  loading,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const map: Record<Variant, string> = {
    yellow: "brutal-btn-yellow",
    blue: "brutal-btn-blue",
    pink: "brutal-btn-pink",
    ghost: "brutal-btn-ghost",
  };
  return (
    <button className={clsx(map[variant], className)} disabled={loading || props.disabled} {...props}>
      {loading && <Loader2 className="animate-spin" size={16} />}
      {children}
    </button>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("brutal-card p-4", className)}>{children}</div>;
}

export function Badge({
  color = "yellow",
  children,
}: {
  color?: "yellow" | "blue" | "pink" | "green" | "red" | "purple";
  children: ReactNode;
}) {
  const map = {
    yellow: "bg-brutal-yellow text-brutal-ink",
    blue: "bg-brutal-blue text-white",
    pink: "bg-brutal-pink text-brutal-ink",
    green: "bg-brutal-green text-brutal-ink",
    red: "bg-brutal-red text-white",
    purple: "bg-brutal-purple text-brutal-ink",
  };
  return <span className={clsx("brutal-badge", map[color])}>{children}</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 font-bold">
      <Loader2 className="animate-spin" size={18} /> {label ?? "Loading..."}
    </div>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "bg-brutal-green" : pct >= 40 ? "bg-brutal-yellow" : "bg-brutal-red";
  return (
    <div className="flex items-center gap-2">
      <div className="h-3 w-24 border border-brutal-border dark:border-brutal-borderDark rounded-full overflow-hidden bg-white dark:bg-brutal-darker">
        <div className={clsx("h-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-bold">{pct}%</span>
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon: ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center opacity-70">
      <div className="mb-2">{icon}</div>
      <p className="font-display text-lg font-bold">{title}</p>
      {hint && <p className="text-sm">{hint}</p>}
    </div>
  );
}
