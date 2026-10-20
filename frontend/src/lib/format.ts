import type { ItemState, InspectionStatus } from "../api";

export const ITEM_LABEL: Record<string, string> = {
  helmet: "Helmet",
  vest: "Hi-vis vest",
  gloves: "Gloves",
  boots: "Safety boots",
  goggles: "Goggles",
  mask: "Mask",
  earmuffs: "Ear protection",
};

export const itemLabel = (k: string) => ITEM_LABEL[k] ?? k;

export const STATE_STYLE: Record<ItemState, { label: string; cls: string; dot: string }> = {
  worn: { label: "Worn", cls: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300", dot: "bg-emerald-500" },
  absent: { label: "Missing", cls: "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300", dot: "bg-red-500" },
  unknown: { label: "Unknown", cls: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300", dot: "bg-amber-500" },
  not_checked: { label: "Not checked", cls: "bg-slate-100 text-slate-500 dark:bg-slate-700/40 dark:text-slate-400", dot: "bg-slate-400" },
};

export const STATUS_STYLE: Record<InspectionStatus, { label: string; cls: string; dot: string }> = {
  compliant: { label: "Compliant", cls: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300", dot: "bg-emerald-500" },
  violation: { label: "Violation", cls: "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300", dot: "bg-red-500" },
  unknown: { label: "Needs review", cls: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300", dot: "bg-amber-500" },
  empty: { label: "No workers", cls: "bg-slate-100 text-slate-500 dark:bg-slate-700/40 dark:text-slate-400", dot: "bg-slate-400" },
};

export function fmtPct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? "–" : `${v.toFixed(digits)}%`;
}

export function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function isoDay(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
