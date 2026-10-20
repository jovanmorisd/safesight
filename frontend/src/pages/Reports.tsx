import { useQuery } from "@tanstack/react-query";
import { FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { Card, PageHeader } from "../components/ui";
import { isoDay } from "../lib/format";

export default function Reports() {
  const today = new Date();
  const [start, setStart] = useState(isoDay(new Date(today.getTime() - 29 * 86400000)));
  const [end, setEnd] = useState(isoDay(today));
  const [siteId, setSiteId] = useState<number | null>(null);
  const { data: sites } = useQuery({ queryKey: ["sites"], queryFn: api.sites });
  const params = { start, end, site_id: siteId };
  const invalid = start > end;

  const reports = [
    {
      kind: "pdf" as const,
      icon: <FileText size={22} />,
      title: "Compliance summary (PDF)",
      text: "KPIs, PPE status per item, the most recent violations with worker crops, and the method & limitations note.",
    },
    {
      kind: "csv" as const,
      icon: <FileSpreadsheet size={22} />,
      title: "Incident log (CSV)",
      text: "Every incident in the period with site, image, missing items, reasons, review status and model version.",
    },
  ];

  return (
    <div>
      <PageHeader title="Generate a report" subtitle="Dates are inclusive and use UTC timestamps." />
      <Card className="mb-5 grid gap-4 p-5 sm:grid-cols-3">
        <label className="space-y-1.5">
          <span className="label-caps">From</span>
          <input type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="space-y-1.5">
          <span className="label-caps">To</span>
          <input type="date" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label className="space-y-1.5">
          <span className="label-caps">Site</span>
          <select className="input" value={siteId ?? ""} onChange={(e) => setSiteId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">All sites</option>
            {sites?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      </Card>
      {invalid && <p className="mb-4 text-sm text-red-500">“From” must be on or before “To”.</p>}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {reports.map((r) => (
          <Card key={r.kind} className="flex flex-col gap-4 p-6">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">{r.icon}</div>
            <div>
              <div className="text-base font-semibold">{r.title}</div>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{r.text}</p>
            </div>
            <a
              href={invalid ? undefined : api.reportUrl(r.kind, params)}
              className={`btn-primary mt-auto self-start ${invalid ? "pointer-events-none opacity-50" : ""}`}
            >
              Download {r.kind.toUpperCase()}
            </a>
          </Card>
        ))}
      </div>
    </div>
  );
}
