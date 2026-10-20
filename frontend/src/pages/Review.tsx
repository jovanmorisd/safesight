import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, ClipboardCheck, ExternalLink, RotateCcw, ShieldX, Wrench } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type Incident } from "../api";
import { Card, EmptyState, ErrorBox, Loading, PageHeader, Segmented, StateChip } from "../components/ui";
import { fmtDateTime, itemLabel } from "../lib/format";

const SEVERITY = {
  high: "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300",
  medium: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  low: "bg-slate-100 text-slate-500 dark:bg-slate-700/40 dark:text-slate-300",
};

function IncidentCard({ x }: { x: Incident }) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState(x.notes);
  const update = useMutation({
    mutationFn: (status: Incident["status"]) => api.updateIncident(x.id, { status, notes }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const reasons = x.person ? x.items.map((it) => `${itemLabel(it)}: ${x.person!.items[it]?.reason ?? ""}`) : [];
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="flex gap-4 p-4">
        <div className="relative h-36 w-28 shrink-0 overflow-hidden rounded-2xl bg-sunken ring-1 ring-line dark:bg-sunken-dark dark:ring-line-dark">
          {x.person?.crop_url && <img src={x.person.crop_url} alt="" className="h-full w-full object-cover" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={clsx("chip capitalize", SEVERITY[x.severity])}>{x.severity}</span>
            <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-700/40 dark:text-slate-300">
              {x.kind === "violation" ? "Violation" : "Needs review"}
            </span>
            <span className="text-xs text-slate-400">#{x.id}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {x.items.map((it) => (
              <StateChip key={it} item={it} state={x.kind === "violation" ? "absent" : "unknown"} />
            ))}
          </div>
          <ul className="mt-2 space-y-0.5 text-xs text-slate-500 dark:text-slate-400">
            {reasons.map((r) => (
              <li key={r} className="truncate" title={r}>
                {r}
              </li>
            ))}
          </ul>
          <div className="mt-2 text-xs text-slate-400">
            {x.site} · worker #{(x.person?.idx ?? 0) + 1} · {fmtDateTime(x.created_at)}
          </div>
          <Link to={`/inspections/${x.inspection_id}`} className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
            Open inspection <ExternalLink size={12} />
          </Link>
        </div>
      </div>
      <div className="mt-auto border-t border-line p-3 dark:border-line-dark">
        <input className="input mb-2 py-1.5 text-xs" placeholder="Reviewer notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {x.status === "open" ? (
          <div className="grid grid-cols-3 gap-2">
            <button className="btn-primary px-2 text-xs" disabled={update.isPending} onClick={() => update.mutate("confirmed")}>
              <Check size={14} /> Confirm
            </button>
            <button className="btn-ghost px-2 text-xs" disabled={update.isPending} onClick={() => update.mutate("false_positive")}>
              <ShieldX size={14} /> False alarm
            </button>
            <button className="btn-ghost px-2 text-xs" disabled={update.isPending} onClick={() => update.mutate("resolved")}>
              <Wrench size={14} /> Resolved
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="text-slate-500">
              <b className="capitalize text-slate-700 dark:text-slate-200">{x.status.replace("_", " ")}</b>
              {x.reviewer && ` by ${x.reviewer}`}
              {x.reviewed_at && ` · ${fmtDateTime(x.reviewed_at)}`}
            </span>
            <button className="btn-ghost px-3 py-1 text-xs" onClick={() => update.mutate("open")}>
              <RotateCcw size={13} /> Reopen
            </button>
          </div>
        )}
        {update.error && <div className="mt-2 text-xs text-red-500">{String(update.error)}</div>}
      </div>
    </Card>
  );
}

export default function Review() {
  const [status, setStatus] = useState("open");
  const [kind, setKind] = useState("");
  const { data, error, isLoading } = useQuery({
    queryKey: ["incidents", status, kind],
    queryFn: () => api.incidents({ status, kind, limit: 200 }),
  });
  const c = data?.counts ?? {};
  return (
    <div>
      <PageHeader
        title="Incidents"
        subtitle="Confirm real violations or mark false alarms — reviewer decisions feed the review-precision metric."
        actions={
          <>
            <Segmented
              size="sm"
              value={kind}
              onChange={setKind}
              options={[
                { value: "", label: "All types" },
                { value: "violation", label: "Violations" },
                { value: "review", label: "Needs review" },
              ]}
            />
            <Segmented
              size="sm"
              value={status}
              onChange={setStatus}
              options={[
                { value: "open", label: "Open", count: c.open ?? 0 },
                { value: "confirmed", label: "Confirmed", count: c.confirmed ?? 0 },
                { value: "false_positive", label: "False alarm", count: c.false_positive ?? 0 },
                { value: "resolved", label: "Resolved", count: c.resolved ?? 0 },
              ]}
            />
          </>
        }
      />
      {isLoading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && data.items.length === 0 && (
        <Card>
          <EmptyState icon={<ClipboardCheck />} title="Queue is clear" text="No incidents in this view." />
        </Card>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {data?.items.map((x) => <IncidentCard key={x.id} x={x} />)}
      </div>
    </div>
  );
}
