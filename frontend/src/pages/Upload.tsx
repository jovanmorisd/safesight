import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowRight, Camera, CheckCircle2, ImagePlus, Trash2, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type InspectionSummary } from "../api";
import { shrinkImages } from "../lib/resize";
import { Card, CardHeader, ErrorBox, Spinner, StateChip, StatusBadge } from "../components/ui";

export default function UploadPage() {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [siteId, setSiteId] = useState<number | null>(null);
  const [results, setResults] = useState<InspectionSummary[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const { data: sites } = useQuery({ queryKey: ["sites"], queryFn: api.sites });
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });

  useEffect(() => {
    if (siteId === null && sites?.length) setSiteId(sites[0].id);
  }, [sites, siteId]);
  const site = sites?.find((s) => s.id === siteId);
  const previews = useMemo(() => files.map((f) => ({ f, url: URL.createObjectURL(f) })), [files]);
  useEffect(() => () => previews.forEach((p) => URL.revokeObjectURL(p.url)), [previews]);

  const run = useMutation({
    mutationFn: async () => api.upload(await shrinkImages(files), siteId),
    onSuccess: (r) => {
      setResults(r.inspections);
      setErrors(r.errors);
      setFiles([]);
      qc.invalidateQueries();
    },
  });

  const add = (list: FileList | null) => {
    if (!list) return;
    const imgs = Array.from(list).filter((f) => f.type.startsWith("image/"));
    setFiles((prev) => [...prev, ...imgs].slice(0, 20));
  };

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-5">
        <Card className="p-5">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              add(e.dataTransfer.files);
            }}
            onClick={() => input.current?.click()}
            className={clsx(
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed px-6 py-14 text-center transition",
              drag ? "border-brand-400 bg-brand-50/60 dark:bg-brand-500/10" : "border-line hover:border-brand-300 hover:bg-sunken dark:border-line-dark dark:hover:bg-sunken-dark",
            )}
          >
            <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow">
              <UploadCloud size={28} />
            </div>
            <div className="text-base font-semibold">
              <span className="hidden sm:inline">Drop site photos here</span>
              <span className="sm:hidden">Choose photos</span>
            </div>
            <div className="text-sm text-slate-500">
              <span className="hidden sm:inline">or click to browse · </span>JPG, PNG, WEBP · up to 20 images, 20 MB each
            </div>
            <input ref={input} type="file" accept="image/*" multiple hidden onChange={(e) => add(e.target.files)} />
          </div>
          <button onClick={() => camera.current?.click()} className="btn-primary mt-3 w-full py-3 sm:hidden">
            <Camera size={18} /> Take a photo
          </button>
          <input
            ref={camera}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => {
              add(e.target.files);
              e.target.value = "";
            }}
          />

          {previews.length > 0 && (
            <div className="mt-5 grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {previews.map(({ f, url }, i) => (
                <div key={i} className="group relative aspect-square overflow-hidden rounded-2xl bg-sunken ring-1 ring-line dark:ring-line-dark">
                  <img src={url} alt={f.name} className="h-full w-full object-cover" />
                  <button
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                    className="absolute right-1.5 top-1.5 rounded-full bg-white/90 p-1 text-slate-600 opacity-0 shadow transition group-hover:opacity-100"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              <button onClick={() => input.current?.click()} className="grid aspect-square place-items-center rounded-2xl border-2 border-dashed border-line text-slate-400 hover:text-brand-600 dark:border-line-dark">
                <ImagePlus size={22} />
              </button>
            </div>
          )}
        </Card>

        {run.isPending && (
          <Card className="flex items-center gap-3 p-5 text-sm">
            <Spinner /> Running detection, pose estimation and compliance checks on {files.length} image{files.length > 1 ? "s" : ""}…
          </Card>
        )}
        {run.error && <ErrorBox error={run.error} />}
        {errors.length > 0 && <ErrorBox error={errors.join("\n")} />}

        {results.length > 0 && (
          <Card className="p-5">
            <CardHeader icon={<CheckCircle2 size={16} />} title={`${results.length} inspection${results.length > 1 ? "s" : ""} complete`} />
            <div className="mt-4 space-y-2">
              {results.map((r) => (
                <Link key={r.id} to={`/inspections/${r.id}`} className="flex items-center gap-3 rounded-2xl bg-sunken p-2.5 transition hover:ring-1 hover:ring-brand-200 dark:bg-sunken-dark">
                  <img src={r.annotated_url} alt="" className="h-14 w-20 rounded-xl object-cover" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{r.filename}</div>
                    <div className="text-xs text-slate-500">
                      {r.num_persons} workers · {r.num_violations} violations · {r.num_unknown} unknown · {Math.round(r.latency_ms)} ms
                    </div>
                  </div>
                  <StatusBadge status={r.status} />
                  <ArrowRight size={16} className="text-slate-400" />
                </Link>
              ))}
            </div>
          </Card>
        )}
      </div>

      <div className="space-y-5">
        <Card className="space-y-5 p-5">
          <div>
            <div className="label-caps mb-2">Site</div>
            <select className="input" value={siteId ?? ""} onChange={(e) => setSiteId(Number(e.target.value))}>
              {sites?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {site && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className="text-xs text-slate-500">Required PPE:</span>
                {site.required_ppe.map((r) => (
                  <StateChip key={r} item={r} state={meta?.pipeline.supported.includes(r) ? "worn" : "not_checked"} title={meta?.pipeline.supported.includes(r) ? "checked" : "active model cannot detect this item"} />
                ))}
              </div>
            )}
          </div>

          <button className="btn-primary w-full py-3" disabled={!files.length || run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? <Spinner className="h-4 w-4 text-white" /> : <UploadCloud size={16} />}
            Inspect {files.length || ""} image{files.length === 1 ? "" : "s"}
          </button>
        </Card>
        {files.length > 0 && !run.isPending && (
          <div className="fixed inset-x-4 bottom-24 z-20 sm:hidden" style={{ marginBottom: "env(safe-area-inset-bottom)" }}>
            <button className="btn-primary w-full py-3.5 shadow-float" onClick={() => run.mutate()}>
              <UploadCloud size={18} /> Inspect {files.length} image{files.length === 1 ? "" : "s"}
            </button>
          </div>
        )}
        <Card className="p-5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          <div className="mb-1 text-sm font-semibold text-slate-700 dark:text-slate-200">How a verdict is made</div>
          Each worker gets a state per PPE item: <b>worn</b>, <b>missing</b>, <b>unknown</b> (the body part is not visible) or <b>not checked</b> (the
          active model cannot detect that item). A violation is raised only when a required item is missing; unknowns go to the review queue.
          {!!meta?.retention_days && (
            <div className="mt-2">
              Photos and results are kept for <b>{meta.retention_days} days</b>, then deleted automatically.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
