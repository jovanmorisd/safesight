import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Clock3,
  Cpu,
  Eye,
  Gauge,
  HardHat,
  Maximize2,
  MoreHorizontal,
  ShieldCheck,
  Upload,
  Users,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, type Stats } from "../api";
import { ArcGauge, PillBars, SegmentedGauge, type BarDatum } from "../components/charts";
import { Card, CardHeader, EmptyState, ErrorBox, Loading, Segmented, StateChip, StatusBadge, TrendChip } from "../components/ui";
import { fmtPct, itemLabel, timeAgo } from "../lib/format";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ITEM_DOT: Record<string, string> = {
  helmet: "bg-brand-600",
  vest: "bg-brand-400",
  gloves: "bg-brand-200",
  boots: "bg-sky-400",
  goggles: "bg-indigo-400",
  mask: "bg-violet-400",
  earmuffs: "bg-slate-400",
};

function KpiCard({
  icon,
  label,
  value,
  chip,
  gauge,
  tone = "brand",
  to,
  active,
  hint,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  chip: ReactNode;
  gauge: number | null;
  tone?: "brand" | "bad" | "warn";
  to: string;
  active?: boolean;
  hint?: string;
}) {
  return (
    <div
      className={clsx(
        "relative h-[124px] overflow-hidden rounded-2xl p-4 transition",
        active
          ? "bg-panel shadow-float ring-1 ring-brand-200 dark:bg-panel-dark dark:ring-brand-500/30"
          : "bg-transparent hover:bg-sunken dark:hover:bg-sunken-dark",
      )}
      title={hint}
    >
      {active && <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand-300 via-brand-500 to-brand-300" />}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-300">
          <span className="grid h-6 w-6 place-items-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">{icon}</span>
          {label}
        </div>
        <Link to={to} className="relative z-10 rounded-full p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white">
          <ArrowUpRight size={16} />
        </Link>
      </div>
      <div className="mt-3 text-[30px] font-semibold leading-none tracking-tight">{value}</div>
      <div className="mt-2.5">{chip}</div>
      <div className="pointer-events-none absolute -bottom-9 -right-3">
        <ArcGauge value={gauge} tone={tone} size={118} />
      </div>
    </div>
  );
}

function Hero({ stats }: { stats: Stats }) {
  const latest = stats.latest;
  if (!latest) {
    return (
      <Card className="relative flex min-h-[300px] items-center justify-center overflow-hidden sm:min-h-[380px]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(45,212,191,.18),transparent_45%),radial-gradient(circle_at_80%_80%,rgba(13,148,136,.15),transparent_40%)]" />
        <EmptyState
          icon={<HardHat />}
          title="No inspections yet"
          text="Upload a construction-site photo. Every worker is checked for the PPE your site policy requires."
          action={
            <Link to="/upload" className="btn-primary">
              <Upload size={16} /> Run first inspection
            </Link>
          }
        />
      </Card>
    );
  }
  return (
    <Card className="group relative min-h-[260px] overflow-hidden sm:min-h-[380px]">
      <img src={latest.annotated_url} alt={latest.filename} className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-[1.02]" />
      <div className="absolute inset-0 bg-gradient-to-t from-slate-950/55 via-transparent to-transparent" />
      <Link
        to={`/inspections/${latest.id}`}
        className="absolute right-3 top-3 flex items-center gap-3 rounded-2xl bg-white/85 px-3 py-2 sm:right-4 sm:top-4 sm:gap-4 sm:px-4 sm:py-3 shadow-float ring-1 ring-white/60 backdrop-blur-md transition hover:bg-white dark:bg-slate-900/75 dark:ring-white/10"
      >
        <div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <Clock3 size={13} /> Latest inspection · {timeAgo(latest.created_at)}
          </div>
          <div className="mt-0.5 text-sm font-semibold">
            {latest.num_persons} worker{latest.num_persons === 1 ? "" : "s"} · {latest.num_violations} violation
            {latest.num_violations === 1 ? "" : "s"}
          </div>
        </div>
        <ArrowRight size={18} />
      </Link>
      <div className="absolute bottom-4 left-4 right-4 flex flex-wrap items-center gap-2">
        <StatusBadge status={latest.status} className="bg-white/90 dark:bg-slate-900/80" />
        <span className="chip bg-white/90 text-slate-700 dark:bg-slate-900/80 dark:text-slate-200">{latest.site}</span>
        {latest.owner && <span className="chip bg-white/90 text-slate-700 dark:bg-slate-900/80 dark:text-slate-200">{latest.owner}</span>}
        <span className="chip ml-auto hidden bg-white/90 text-slate-500 sm:inline-flex dark:bg-slate-900/80 dark:text-slate-300">{latest.filename}</span>
      </div>
    </Card>
  );
}

function TrendCard({ stats, days, setDays }: { stats: Stats; days: number; setDays: (d: number) => void }) {
  const [mode, setMode] = useState<"daily" | "monthly">("daily");
  const bars: BarDatum[] = useMemo(() => {
    if (mode === "monthly") {
      return stats.monthly.map((p) => ({
        key: p.key,
        label: MONTHS[Number(p.key.slice(5, 7)) - 1],
        value: p.violations,
        detail: `${p.compliant} compliant · ${p.unknown} unknown${p.rate !== null ? ` · ${p.rate}% compliance` : ""}`,
      }));
    }
    return stats.daily.map((p) => {
      const d = new Date(p.key + "T00:00:00");
      return {
        key: p.key,
        label: days <= 14 ? d.toLocaleDateString(undefined, { weekday: "short" }) : String(d.getDate()),
        value: p.violations,
        detail: `${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })} · ${p.compliant} compliant${p.rate !== null ? ` · ${p.rate}%` : ""}`,
      };
    });
  }, [stats, mode, days]);
  const series = mode === "monthly" ? stats.monthly : stats.daily;
  const highlight = [...series].reverse().find((p) => p.violations > 0)?.key ?? series[series.length - 1]?.key;
  const k = stats.kpis;

  const items = Object.entries(stats.per_item)
    .map(([item, c]) => ({ item, ...c, assessed: c.worn + c.absent }))
    .filter((x) => x.assessed > 0)
    .sort((a, b) => b.assessed - a.assessed);

  return (
    <Card className="p-5">
      <CardHeader
        title={<span className="text-[15px] text-slate-700 dark:text-slate-200">Violations over time</span>}
        action={
          <div className="flex items-center gap-2">
            <Segmented
              size="sm"
              value={String(days)}
              onChange={(v) => setDays(Number(v))}
              options={[
                { value: "7", label: "7d" },
                { value: "30", label: "30d" },
                { value: "90", label: "90d" },
              ]}
            />
            <Link to="/inspections" className="rounded-full p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-white" title="All inspections">
              <Maximize2 size={16} />
            </Link>
          </div>
        }
      />
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
        <div className="card-sunken p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[28px] font-semibold tracking-tight">{k.violations}</span>
                <span className="text-sm text-slate-500">violations</span>
                <TrendChip value={k.incidents_delta} suffix="" good={k.incidents_delta <= 0} />
              </div>
              <div className="text-xs text-slate-400">
                {k.persons} workers assessed in {k.inspections} inspection{k.inspections === 1 ? "" : "s"} · last {days} days
              </div>
            </div>
            <Segmented
              size="sm"
              value={mode}
              onChange={setMode}
              options={[
                { value: "daily", label: "Daily" },
                { value: "monthly", label: "Monthly" },
              ]}
            />
          </div>
          <div className="mt-5">
            <PillBars data={bars} highlight={highlight} height={200} />
          </div>
        </div>

        <div className="card-sunken flex flex-col p-5">
          <CardHeader
            title={<span className="text-slate-700 dark:text-slate-200">PPE compliance</span>}
            action={
              <Link to="/reports" className="text-slate-400 hover:text-slate-700 dark:hover:text-white">
                <MoreHorizontal size={18} />
              </Link>
            }
          />
          <div className="relative mx-auto mt-1">
            <SegmentedGauge value={k.compliance_rate} size={230} />
            <div className="absolute inset-x-0 text-center" style={{ top: 230 * 0.56 - 30 }}>
              <div className="text-[26px] font-semibold leading-tight tracking-tight">{fmtPct(k.compliance_rate)}</div>
              <div className="text-[11px] text-slate-400">workers compliant</div>
            </div>
          </div>
          <div className="mt-3 space-y-2.5">
            {items.length === 0 && <p className="text-center text-xs text-slate-400">No required PPE assessed in this period.</p>}
            {items.slice(0, 4).map((x) => (
              <div key={x.item} className="flex items-center gap-2 text-sm">
                <span className={clsx("h-2 w-2 rounded-full", ITEM_DOT[x.item] ?? "bg-slate-400")} />
                <span className="flex-1 text-slate-600 dark:text-slate-300">{itemLabel(x.item)}</span>
                <span className="text-xs text-slate-400">
                  {x.worn}/{x.assessed}
                </span>
                <span className="w-12 text-right font-semibold">{Math.round((100 * x.worn) / x.assessed)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

function RecentIncidents() {
  const { data } = useQuery({ queryKey: ["incidents", "open", "recent"], queryFn: () => api.incidents({ status: "open", limit: 5 }) });
  return (
    <Card className="p-5">
      <CardHeader
        icon={<AlertTriangle size={16} />}
        title="Open incidents"
        action={
          <Link to="/review" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
            Review all
          </Link>
        }
      />
      <div className="mt-4 divide-y divide-line dark:divide-line-dark">
        {!data?.items.length && <p className="py-8 text-center text-sm text-slate-400">Nothing waiting for review.</p>}
        {data?.items.map((x) => (
          <Link key={x.id} to={`/inspections/${x.inspection_id}`} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
            {x.person?.crop_url ? (
              <img src={x.person.crop_url} className="h-12 w-12 rounded-xl object-cover ring-1 ring-line dark:ring-line-dark" alt="" />
            ) : (
              <div className="h-12 w-12 rounded-xl bg-sunken" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap gap-1">
                {x.items.map((it) => (
                  <StateChip key={it} item={it} state={x.kind === "violation" ? "absent" : "unknown"} />
                ))}
              </div>
              <div className="mt-1 truncate text-xs text-slate-400">
                {x.site} · worker #{(x.person?.idx ?? 0) + 1} · {timeAgo(x.created_at)}
              </div>
            </div>
            <span
              className={clsx(
                "chip capitalize",
                x.severity === "high" ? "bg-red-50 text-red-600 dark:bg-red-500/10" : x.severity === "medium" ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10" : "bg-slate-100 text-slate-500 dark:bg-slate-700/40",
              )}
            >
              {x.severity}
            </span>
          </Link>
        ))}
      </div>
    </Card>
  );
}

function ModelCard({ stats }: { stats: Stats }) {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const k = stats.kpis;
  const rows = [
    { icon: <Cpu size={15} />, label: "Runtime", value: meta ? `CPU · ${meta.pipeline.runtime ?? "ONNX"}` : "–" },
    { icon: <Gauge size={15} />, label: "Avg. latency", value: k.avg_latency_ms ? `${Math.round(k.avg_latency_ms)} ms` : "–" },
    { icon: <ShieldCheck size={15} />, label: "Review precision", value: k.review_precision !== null ? `${k.review_precision}% (${k.reviewed} reviewed)` : "no reviews yet" },
    { icon: <Users size={15} />, label: "Workers assessed", value: String(k.persons) },
  ];
  return (
    <Card className="p-5">
      <CardHeader
        icon={<Cpu size={16} />}
        title="Active model"
        action={
          <Link to="/models" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
            Manage
          </Link>
        }
      />
      <div className="mt-4 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-800 p-4 text-white shadow-glow">
        <div className="text-xs text-white/70">Detector{(meta?.pipeline.detectors.length ?? 0) > 1 ? "s" : ""}</div>
        <div className="truncate text-base font-semibold">{meta?.pipeline.detectors.map((d) => d.name).join(" + ") ?? "…"}</div>
        <div className="mt-3 flex flex-wrap gap-1">
          {meta?.pipeline.supported.map((s) => (
            <span key={s} className="chip bg-white/15 text-white">
              {itemLabel(s)}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-4 space-y-3">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-2 text-sm">
            <span className="text-slate-400">{r.icon}</span>
            <span className="flex-1 text-slate-500 dark:text-slate-400">{r.label}</span>
            <span className="font-medium">{r.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const { data: stats, error, isLoading } = useQuery({
    queryKey: ["stats", days],
    queryFn: () => api.stats(days),
    refetchInterval: 30_000,
  });
  if (isLoading) return <Loading />;
  if (error || !stats) return <ErrorBox error={error ?? "No data"} />;
  const k = stats.kpis;
  const openShare = k.incidents_opened ? Math.min(100, (100 * k.open_incidents) / Math.max(k.open_incidents, k.incidents_opened)) : 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="space-y-1 p-2">
          <KpiCard
            active
            icon={<ShieldCheck size={14} />}
            label="Compliance rate"
            value={fmtPct(k.compliance_rate)}
            chip={<TrendChip value={k.compliance_delta} good={(k.compliance_delta ?? 0) >= 0} />}
            gauge={k.compliance_rate}
            to="/inspections?status=compliant"
            hint="Compliant workers / (compliant + violation) in the selected period"
          />
          <KpiCard
            icon={<AlertTriangle size={14} />}
            label="Open incidents"
            value={String(k.open_incidents)}
            chip={<TrendChip value={k.incidents_delta} suffix=" new" good={k.incidents_delta <= 0} />}
            gauge={openShare}
            tone="bad"
            to="/review"
            hint="Incidents waiting for a reviewer; the gauge shows the share of this period's incidents still open"
          />
          <KpiCard
            icon={<Eye size={14} />}
            label="Unknown rate"
            value={fmtPct(k.unknown_rate)}
            chip={<TrendChip value={k.unknown_delta} good={(k.unknown_delta ?? 0) <= 0} />}
            gauge={k.unknown_rate}
            tone="warn"
            to="/inspections?status=unknown"
            hint="Workers whose required PPE could not be judged (head/body not visible, too small)"
          />
        </Card>
        <Hero stats={stats} />
      </div>

      <TrendCard stats={stats} days={days} setDays={setDays} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <RecentIncidents />
        <ModelCard stats={stats} />
      </div>
    </div>
  );
}
