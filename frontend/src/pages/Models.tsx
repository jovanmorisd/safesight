import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Boxes, CheckCircle2, Plus, Trash2, UploadCloud } from "lucide-react";
import { useState } from "react";
import { api, type ModelVersion } from "../api";
import { Card, CardHeader, ErrorBox, Loading, PageHeader, Spinner } from "../components/ui";
import { ITEM_LABEL, fmtDateTime, itemLabel } from "../lib/format";

function ModelRow({ m }: { m: ModelVersion }) {
  const qc = useQueryClient();
  const [showClasses, setShowClasses] = useState(false);
  const update = useMutation({
    mutationFn: (body: { is_active: boolean; exclusive: boolean }) => api.updateModel(m.id, body),
    onSuccess: () => qc.invalidateQueries(),
  });
  const del = useMutation({ mutationFn: () => api.deleteModel(m.id), onSuccess: () => qc.invalidateQueries() });
  return (
    <Card className={clsx("p-5", m.is_active && "ring-2 ring-brand-300 dark:ring-brand-500/40")}>
      <div className="flex flex-wrap items-start gap-3">
        <div className={clsx("grid h-11 w-11 place-items-center rounded-2xl", m.is_active ? "bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow" : "bg-sunken text-slate-500 dark:bg-sunken-dark")}>
          <Boxes size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold">{m.name}</span>
            {m.is_active && (
              <span className="chip bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
                <CheckCircle2 size={12} /> Active
              </span>
            )}
          </div>
          <div className="mt-0.5 truncate text-xs text-slate-400">
            {m.weights_path} · sha {m.sha256} · conf {m.conf} · {m.imgsz}px · added {fmtDateTime(m.created_at)}
          </div>
          {m.notes && <div className="mt-1 text-xs text-slate-500">{m.notes}</div>}
        </div>
        <div className="flex gap-2">
          {!m.is_active ? (
            <>
              <button className="btn-primary" disabled={update.isPending} onClick={() => update.mutate({ is_active: true, exclusive: true })}>
                {update.isPending ? <Spinner className="h-4 w-4 text-white" /> : null} Activate
              </button>
              <button className="btn-ghost" disabled={update.isPending} onClick={() => update.mutate({ is_active: true, exclusive: false })} title="Run together with the current active model(s)">
                <Plus size={14} /> Add to ensemble
              </button>
              <button className="btn-danger px-3" onClick={() => window.confirm(`Delete model ${m.name}?`) && del.mutate()}>
                <Trash2 size={14} />
              </button>
            </>
          ) : (
            <button className="btn-ghost" disabled={update.isPending} onClick={() => update.mutate({ is_active: false, exclusive: false })}>
              Deactivate
            </button>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs text-slate-500">Detects:</span>
        {Object.keys(ITEM_LABEL).map((it) => (
          <span
            key={it}
            className={clsx(
              "chip",
              m.supported.includes(it) ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-slate-100 text-slate-400 line-through dark:bg-slate-700/40",
            )}
          >
            {itemLabel(it)}
          </span>
        ))}
        <button className="ml-auto text-xs font-medium text-brand-700 hover:underline dark:text-brand-300" onClick={() => setShowClasses(!showClasses)}>
          {showClasses ? "Hide" : "Show"} {m.classes.length} model classes
        </button>
      </div>
      {showClasses && (
        <div className="mt-3 flex flex-wrap gap-1">
          {m.classes.map((c) => {
            const mapped = m.class_map?.[c];
            return (
              <span key={c} className="chip bg-sunken text-slate-600 ring-1 ring-line dark:bg-sunken-dark dark:text-slate-300 dark:ring-line-dark">
                {c}
                {mapped && ` → ${mapped}`}
              </span>
            );
          })}
          <p className="mt-1 w-full text-[11px] text-slate-400">
            {m.class_map ? "Explicit class map." : "No explicit class map: classes are mapped automatically by name (helmet/hardhat, safety-vest, shoes→boots, …)."}
          </p>
        </div>
      )}
      {(update.error || del.error) && <div className="mt-3"><ErrorBox error={update.error ?? del.error} /></div>}
    </Card>
  );
}

const MAX_MODEL_MB = 50; // Supabase free plan: max file size per upload

/** PUT a file with upload progress (fetch has no upload progress events). */
function putWithProgress(url: string, file: File, onProgress: (pct: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.withCredentials = url.startsWith("/");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    if (!url.startsWith("/")) xhr.setRequestHeader("x-upsert", "true");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((100 * e.loaded) / e.total));
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload failed (${xhr.status}): ${xhr.responseText.slice(0, 160)}`)));
    xhr.onerror = () => reject(new Error("Upload failed: network error"));
    xhr.send(file);
  });
}

function RegisterForm() {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [conf, setConf] = useState("0.35");
  const [cmap, setCmap] = useState("");
  const [notes, setNotes] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const tooBig = !!file && file.size > MAX_MODEL_MB * 1024 * 1024;
  const wrongType = !!file && !file.name.toLowerCase().endsWith(".onnx");

  const reg = useMutation({
    mutationFn: async () => {
      let classMap: Record<string, string> | null = null;
      if (cmap.trim()) {
        try {
          classMap = JSON.parse(cmap);
        } catch {
          throw new Error('Class map must be JSON, e.g. {"Hardhat": "helmet"}');
        }
      }
      const up = await api.modelUploadUrl(name.trim());
      setProgress(0);
      await putWithProgress(up.url, file!, setProgress);
      setProgress(100);
      return api.registerModel({ name: name.trim(), key: up.key, conf: Number(conf), class_map: classMap, notes });
    },
    onSuccess: () => {
      setFile(null);
      setName("");
      setCmap("");
      setNotes("");
      setProgress(null);
      qc.invalidateQueries();
    },
    onError: () => setProgress(null),
  });
  return (
    <Card className="p-5">
      <CardHeader icon={<UploadCloud size={16} />} title="Register a trained model" />
      <p className="mt-1 text-xs text-slate-500">
        In your notebook run <code className="rounded bg-sunken px-1 dark:bg-sunken-dark">model.export(format="onnx")</code> and upload the{" "}
        <code>.onnx</code> file. It goes straight to storage, is checked once (class names are read from the file), then you activate it.
      </p>
      <div className="mt-4 space-y-3">
        <label className="flex cursor-pointer items-center gap-3 rounded-2xl border-2 border-dashed border-line p-3 text-sm hover:border-brand-300 dark:border-line-dark">
          <UploadCloud size={18} className="shrink-0 text-brand-600" />
          <span className="truncate">{file ? `${file.name} · ${(file.size / 1e6).toFixed(1)} MB` : "Choose a .onnx model"}</span>
          <input type="file" accept=".onnx" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        {wrongType && <p className="text-xs text-red-500">Please choose an .onnx file (export it from your .pt with Ultralytics).</p>}
        {tooBig && (
          <p className="text-xs text-red-500">
            Larger than {MAX_MODEL_MB} MB (the storage limit). Use a smaller model (YOLO n/s) or export with <code>half=True</code>.
          </p>
        )}
        <input className="input" placeholder="Name, e.g. yolo11s-construction-v1" value={name} onChange={(e) => setName(e.target.value)} />
        <label className="flex items-center gap-3 text-sm">
          <span className="w-28 text-slate-500">Confidence</span>
          <input className="input" type="number" step="0.05" min="0.05" max="0.95" value={conf} onChange={(e) => setConf(e.target.value)} />
        </label>
        <textarea
          className="input min-h-[80px] font-mono text-xs"
          placeholder='Optional class map JSON, e.g. {"Hardhat": "helmet", "Safety Vest": "vest", "Person": "person"}'
          value={cmap}
          onChange={(e) => setCmap(e.target.value)}
        />
        <input className="input" placeholder="Notes (dataset, epochs, mAP…)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {progress !== null && (
          <div className="space-y-1">
            <div className="h-2 overflow-hidden rounded-full bg-sunken dark:bg-sunken-dark">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600 transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-[11px] text-slate-500">{progress < 100 ? `Uploading… ${progress}%` : "Checking the model…"}</p>
          </div>
        )}
        <button
          className="btn-primary w-full"
          disabled={!file || wrongType || tooBig || name.trim().length < 2 || reg.isPending}
          onClick={() => reg.mutate()}
        >
          {reg.isPending ? <Spinner className="h-4 w-4 text-white" /> : <Plus size={16} />} Register model
        </button>
        {reg.error && <ErrorBox error={reg.error} />}
        {reg.data && <p className="text-xs text-emerald-600">Registered {reg.data.name}: detects {reg.data.supported.join(", ") || "no known PPE classes"}.</p>}
      </div>
    </Card>
  );
}

export default function Models() {
  const { data, error, isLoading } = useQuery({ queryKey: ["models"], queryFn: api.models });
  return (
    <div>
      <PageHeader title="Model registry" subtitle="Swap the pretrained detectors for your own trained ONNX models without touching code." />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          {isLoading && <Loading />}
          {error && <ErrorBox error={error} />}
          {data?.map((m) => <ModelRow key={m.id} m={m} />)}
        </div>
        <div className="space-y-5">
          <RegisterForm />
          <Card className="p-5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            <div className="mb-1 text-sm font-semibold text-slate-700 dark:text-slate-200">Missing classes are safe</div>
            If a model cannot detect an item a site requires, that item is reported as <b>not checked</b> for every worker and never produces a
            violation. Use <b>Add to ensemble</b> to combine, for example, a helmet/vest model with a gloves/boots model.
          </Card>
        </div>
      </div>
    </div>
  );
}
