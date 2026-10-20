import { useQuery } from "@tanstack/react-query";
import { Cpu, GitBranch, Layers } from "lucide-react";
import { api } from "../api";
import { Card, CardHeader, ErrorBox, Loading, PageHeader } from "../components/ui";
import { itemLabel } from "../lib/format";

const STEPS = [
  ["PPE detector(s)", "YOLO models exported to ONNX (run with ONNX Runtime) from the model registry; class names mapped to canonical PPE items."],
  ["Pose model", "Person boxes + 17 COCO keypoints (head, shoulders, wrists, hips, ankles)."],
  ["Person-level association", "Matches each PPE box to a body region (from keypoints) of a specific worker; Hungarian matching for one-per-person items."],
  ["Policy", "Site-required items decide the verdict: violation only when a required item is missing."],
  ["Storage & review", "Original, annotated image, worker crops and incidents are stored for review and reporting."],
];

export default function System() {
  const { data, error, isLoading } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error ?? "unavailable"} />;
  const p = data.pipeline;
  return (
    <div>
      <PageHeader title="System" subtitle="What is running behind each inspection." />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <CardHeader icon={<Cpu size={16} />} title="Runtime" />
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Device</dt>
              <dd className="font-medium">CPU · {p.runtime ?? "ONNX Runtime"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Pose model</dt>
              <dd className="font-medium">{p.pose ?? "disabled"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Database</dt>
              <dd className="font-medium">{data.database === "postgresql" ? "Postgres (Supabase)" : "SQLite (local file)"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Image storage</dt>
              <dd className="font-medium">{data.storage === "supabase" ? "Supabase Storage (private bucket)" : "Local folder"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Auto-delete</dt>
              <dd className="font-medium">{data.retention_days > 0 ? `after ${data.retention_days} days` : "off"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Detectable PPE</dt>
              <dd className="text-right font-medium">{p.supported.map(itemLabel).join(", ")}</dd>
            </div>
          </dl>
        </Card>
        <Card className="p-5">
          <CardHeader icon={<GitBranch size={16} />} title="Pipeline" />
          <ol className="mt-4 space-y-3">
            {STEPS.map(([t, d], i) => (
              <li key={t} className="flex gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">{i + 1}</span>
                <div>
                  <div className="text-sm font-medium">{t}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{d}</div>
                </div>
              </li>
            ))}
          </ol>
        </Card>
        {p.detectors.map((d) => (
          <Card key={d.name} className="p-5 lg:col-span-2">
            <CardHeader icon={<Layers size={16} />} title={`Detector: ${d.name}`} />
            <div className="mt-1 break-all text-xs text-slate-400">{d.weights}</div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {d.classes.map((c) => (
                <span key={c} className={`chip ring-1 ${d.class_map[c] ? "bg-brand-50 text-brand-800 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-200 dark:ring-brand-500/20" : "bg-sunken text-slate-400 ring-line dark:bg-sunken-dark dark:ring-line-dark"}`}>
                  {c}
                  {d.class_map[c] && ` → ${d.class_map[c]}`}
                </span>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-slate-400">Grey classes are ignored by the compliance logic.</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
