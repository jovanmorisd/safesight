import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Cpu, Timer, Trash2, UserRound, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type InspectionDetail as Detail, type PersonOut } from "../api";
import { Card, CardHeader, ErrorBox, Loading, Segmented, StateChip, StatusBadge } from "../components/ui";
import { STATE_STYLE, fmtDateTime, itemLabel } from "../lib/format";

function PersonCard({ p, d, onHover, active }: { p: PersonOut; d: Detail; onHover: (id: number | null) => void; active: boolean }) {
  const shown = d.required.filter((k) => p.items[k]).map((k) => [k, p.items[k]] as const);
  const extra = Object.entries(p.items).filter(([k, v]) => !d.required.includes(k) && v.state !== "not_checked");
  return (
    <div
      onMouseEnter={() => onHover(p.id)}
      onMouseLeave={() => onHover(null)}
      className={clsx(
        "rounded-2xl p-3 ring-1 transition",
        active ? "bg-brand-50/60 ring-brand-300 dark:bg-brand-500/10 dark:ring-brand-500/40" : "bg-sunken ring-transparent dark:bg-sunken-dark",
      )}
    >
      <div className="flex gap-3">
        <img src={p.crop_url} alt="" className="h-20 w-16 shrink-0 rounded-xl bg-white object-cover ring-1 ring-line dark:ring-line-dark" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold">Worker #{p.idx + 1}</div>
            <StatusBadge status={p.overall} />
          </div>
          <div className="mt-0.5 text-[11px] text-slate-400">
            person conf {p.conf.toFixed(2)} · {p.has_pose ? "pose keypoints" : "box only"}
          </div>
          <div className="mt-2 space-y-1.5">
            {shown.map(([item, info]) => (
              <div key={item} className="flex items-start gap-2 text-xs">
                <span className={clsx("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", STATE_STYLE[info.state].dot)} />
                <span className="w-24 shrink-0 font-medium">{itemLabel(item)}</span>
                <span className="min-w-0 flex-1 text-slate-500 dark:text-slate-400">
                  <span className="font-medium text-slate-700 dark:text-slate-200">{STATE_STYLE[info.state].label}</span>
                  {info.reason && ` — ${info.reason}`}
                  {info.conf !== null && info.state === "worn" && ` (${info.conf.toFixed(2)})`}
                </span>
              </div>
            ))}
          </div>
          {extra.length > 0 && (
            <div className="mt-2.5 flex flex-wrap items-center gap-1 border-t border-line pt-2 dark:border-line-dark">
              <span className="mr-0.5 text-[10px] uppercase tracking-wide text-slate-400">Not required</span>
              {extra.map(([item, info]) => (
                <span
                  key={item}
                  title={`${STATE_STYLE[info.state].label}: ${info.reason}`}
                  className={clsx(
                    "chip",
                    info.state === "worn"
                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
                      : "bg-slate-100 text-slate-400 dark:bg-slate-700/40",
                  )}
                >
                  {itemLabel(item)}
                  {info.state === "worn" ? " ✓" : info.state === "unknown" ? " ?" : ""}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function InspectionDetail() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [view, setView] = useState<"annotated" | "original">("annotated");
  const [hover, setHover] = useState<number | null>(null);
  const { data: d, error, isLoading } = useQuery({ queryKey: ["inspection", id], queryFn: () => api.inspection(id) });
  const del = useMutation({
    mutationFn: () => api.deleteInspection(id),
    onSuccess: () => {
      qc.invalidateQueries();
      nav("/inspections");
    },
  });

  if (isLoading) return <Loading />;
  if (error || !d) return <ErrorBox error={error ?? "Not found"} />;

  const meta = [
    { icon: <Users size={14} />, text: `${d.num_persons} worker${d.num_persons === 1 ? "" : "s"}` },
    { icon: <Cpu size={14} />, text: d.model_label },
    ...(d.owner ? [{ icon: <UserRound size={14} />, text: d.owner }] : []),
    { icon: <Timer size={14} />, text: `${Math.round(d.latency_ms)} ms (detect ${Math.round(d.timings.detect ?? 0)}, pose ${Math.round(d.timings.pose ?? 0)})` },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/inspections" className="btn-ghost px-3">
          <ArrowLeft size={16} />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="max-w-full truncate text-base font-semibold sm:text-lg">{d.filename}</h2>
            <StatusBadge status={d.status} />
          </div>
          <div className="text-xs text-slate-500">
            #{d.id} · {d.site} · {fmtDateTime(d.created_at)}
          </div>
        </div>
        <button
          className="btn-danger"
          onClick={() => window.confirm("Delete this inspection, its images and incidents?") && del.mutate()}
          disabled={del.isPending}
        >
          <Trash2 size={16} /> <span className="hidden sm:inline">Delete</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
              {meta.map((m, i) => (
                <span key={i} className="inline-flex items-center gap-1.5">
                  {m.icon}
                  {m.text}
                </span>
              ))}
            </div>
            <Segmented
              size="sm"
              value={view}
              onChange={setView}
              options={[
                { value: "annotated", label: "Annotated" },
                { value: "original", label: "Original" },
              ]}
            />
          </div>
          <div className="flex justify-center overflow-hidden rounded-2xl bg-slate-950">
            <div className="relative">
            <img src={view === "annotated" ? d.annotated_url : d.image_url} alt={d.filename} className="block max-h-[72vh] max-w-full" />
            <div className="pointer-events-none absolute inset-0">
              {d.persons.map((p) => (
                <div
                  key={p.id}
                  className={clsx("absolute rounded-md transition", hover === p.id ? "ring-4 ring-brand-300/90" : "ring-0")}
                  style={{
                    left: `${(p.box[0] / d.width) * 100}%`,
                    top: `${(p.box[1] / d.height) * 100}%`,
                    width: `${((p.box[2] - p.box[0]) / d.width) * 100}%`,
                    height: `${((p.box[3] - p.box[1]) / d.height) * 100}%`,
                  }}
                />
              ))}
            </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
            <span>Required here:</span>
            {d.required.map((r) => (
              <StateChip key={r} item={r} state={d.supported.includes(r) ? "worn" : "not_checked"} title={d.supported.includes(r) ? "checked by the active model" : "the model cannot detect this item"} />
            ))}
          </div>
        </Card>

        <Card className="flex flex-col p-4 xl:max-h-[calc(72vh+90px)]">
          <CardHeader icon={<Users size={16} />} title={`Workers (${d.persons.length})`} />
          <div className="mt-3 flex-1 space-y-2.5 pr-1 scrollbar-thin xl:overflow-y-auto">
            {d.persons.length === 0 && <p className="py-10 text-center text-sm text-slate-400">No workers detected in this image.</p>}
            {d.persons.map((p) => (
              <PersonCard key={p.id} p={p} d={d} onHover={setHover} active={hover === p.id} />
            ))}
          </div>
          {d.incidents.length > 0 && (
            <Link to="/review" className="mt-3 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20">
              {d.incidents.length} incident{d.incidents.length > 1 ? "s" : ""} created → open review queue
            </Link>
          )}
        </Card>
      </div>

    </div>
  );
}
