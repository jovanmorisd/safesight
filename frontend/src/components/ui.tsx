import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import type { InspectionStatus, ItemState } from "../api";
import { STATE_STYLE, STATUS_STYLE, itemLabel } from "../lib/format";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("card", className)}>{children}</div>;
}

export function CardHeader({
  icon,
  title,
  action,
  className,
}: {
  icon?: ReactNode;
  title: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-center justify-between gap-3", className)}>
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-300">
        {icon && <span className="text-brand-600 dark:text-brand-400">{icon}</span>}
        {title}
      </div>
      {action}
    </div>
  );
}

export function StatusBadge({ status, className }: { status: InspectionStatus; className?: string }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={clsx("chip", s.cls, className)}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}

export function StateChip({ item, state, title }: { item: string; state: ItemState; title?: string }) {
  const s = STATE_STYLE[state];
  return (
    <span className={clsx("chip", s.cls)} title={title}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {itemLabel(item)}
    </span>
  );
}

/** Small trend pill like "↗ 7.3%". `good` decides the colour independent of direction. */
export function TrendChip({ value, suffix = "%", good }: { value: number | null; suffix?: string; good?: boolean }) {
  if (value === null || value === undefined) return <span className="chip bg-slate-100 text-slate-400 dark:bg-slate-800">no prior data</span>;
  const up = value >= 0;
  const positive = good ?? up;
  return (
    <span
      className={clsx(
        "chip",
        positive
          ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300"
          : "bg-red-50 text-red-500 dark:bg-red-500/10 dark:text-red-300",
      )}
    >
      {up ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {Math.abs(value).toFixed(suffix === "%" ? 1 : 0)}
      {suffix}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("animate-spin text-brand-500", className)} size={20} />;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Spinner /> {label}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600 ring-1 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
        {icon}
      </div>
      <div className="text-base font-semibold">{title}</div>
      {text && <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">{text}</p>}
      {action}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  size = "md",
}: {
  value: T;
  options: { value: T; label: ReactNode; count?: number }[];
  onChange: (v: T) => void;
  size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex max-w-full gap-1 overflow-x-auto rounded-full bg-sunken p-1 ring-1 ring-line scrollbar-none dark:bg-sunken-dark dark:ring-line-dark">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full font-medium transition",
            size === "sm" ? "px-3 py-1 text-xs" : "px-4 py-1.5 text-sm",
            value === o.value
              ? "bg-panel text-slate-900 shadow-card dark:bg-panel-dark dark:text-white"
              : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
          )}
        >
          {o.label}
          {o.count !== undefined && (
            <span
              className={clsx(
                "rounded-full px-1.5 text-[10px]",
                value === o.value ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300" : "bg-black/5 dark:bg-white/10",
              )}
            >
              {o.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex max-w-full flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
