import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { HardHat, MapPin, Plus, Save } from "lucide-react";
import { useState } from "react";
import { api, type Site } from "../api";
import { Card, CardHeader, ErrorBox, Loading, PageHeader } from "../components/ui";
import { useMe } from "../lib/auth";
import { ITEM_LABEL, itemLabel } from "../lib/format";

function PpePicker({ value, onChange, supported, readOnly }: { value: string[]; onChange: (v: string[]) => void; supported: string[]; readOnly?: boolean }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.keys(ITEM_LABEL).map((it) => {
        const on = value.includes(it);
        return (
          <button
            key={it}
            type="button"
            disabled={readOnly}
            onClick={() => onChange(on ? value.filter((v) => v !== it) : [...value, it])}
            className={clsx(
              "chip px-3 py-1 text-xs ring-1 transition",
              on ? "bg-brand-600 text-white ring-brand-600" : "bg-panel text-slate-500 ring-line hover:ring-brand-300 dark:bg-panel-dark dark:ring-line-dark",
            )}
            title={supported.includes(it) ? "detectable by the active model" : "the active model cannot detect this — it will show as not checked"}
          >
            {itemLabel(it)}
            {!supported.includes(it) && <span className="opacity-70">·n/a</span>}
          </button>
        );
      })}
    </div>
  );
}

function SiteCard({ s, supported, readOnly }: { s: Site; supported: string[]; readOnly: boolean }) {
  const qc = useQueryClient();
  const [req, setReq] = useState(s.required_ppe);
  const [name, setName] = useState(s.name);
  const [loc, setLoc] = useState(s.location);
  const dirty = name !== s.name || loc !== s.location || req.join() !== s.required_ppe.join();
  const save = useMutation({
    mutationFn: () => api.updateSite(s.id, { name, location: loc, required_ppe: req }),
    onSuccess: () => qc.invalidateQueries(),
  });
  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
          <HardHat size={20} />
        </div>
        <div className="grid flex-1 gap-2 sm:grid-cols-2">
          <input className="input font-medium" value={name} readOnly={readOnly} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="Location" value={loc} readOnly={readOnly} onChange={(e) => setLoc(e.target.value)} />
        </div>
      </div>
      <div>
        <div className="label-caps mb-2">Required PPE</div>
        <PpePicker value={req} onChange={setReq} supported={supported} readOnly={readOnly} />
      </div>
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span className="inline-flex items-center gap-1">
          <MapPin size={12} /> {s.inspections} inspection{s.inspections === 1 ? "" : "s"}
        </span>
        {!readOnly && (
          <button className="btn-primary px-3 py-1.5 text-xs" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
            <Save size={13} /> Save
          </button>
        )}
      </div>
      {save.error && <ErrorBox error={save.error} />}
    </Card>
  );
}

export default function Sites() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["sites"], queryFn: api.sites });
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const supported = meta?.pipeline.supported ?? [];
  const { isAdmin } = useMe();
  const [name, setName] = useState("");
  const [loc, setLoc] = useState("");
  const [req, setReq] = useState<string[]>(["helmet", "vest"]);
  const create = useMutation({
    mutationFn: () => api.createSite({ name, location: loc, required_ppe: req }),
    onSuccess: () => {
      setName("");
      setLoc("");
      qc.invalidateQueries();
    },
  });
  return (
    <div>
      <PageHeader
        title="Sites & PPE policies"
        subtitle={
          isAdmin
            ? "Each site decides which PPE is mandatory; only those items can raise violations."
            : "The PPE each site requires. Only an admin can change these policies."
        }
      />
      <div className={isAdmin ? "grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]" : "grid grid-cols-1 gap-5"}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {isLoading && <Loading />}
          {error && <ErrorBox error={error} />}
          {data?.map((s) => <SiteCard key={s.id} s={s} supported={supported} readOnly={!isAdmin} />)}
        </div>
        {isAdmin && (
        <Card className="h-fit space-y-3 p-5">
          <CardHeader icon={<Plus size={16} />} title="Add a site" />
          <input className="input" placeholder="Site name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="Location (optional)" value={loc} onChange={(e) => setLoc(e.target.value)} />
          <PpePicker value={req} onChange={setReq} supported={supported} />
          <button className="btn-primary w-full" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
            <Plus size={16} /> Create site
          </button>
          {create.error && <ErrorBox error={create.error} />}
        </Card>
        )}
      </div>
    </div>
  );
}
