import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Images, Upload, Users, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Card, EmptyState, ErrorBox, Loading, PageHeader, Segmented, StatusBadge } from "../components/ui";
import { timeAgo } from "../lib/format";

const PAGE = 24;

export default function Inspections() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const q = params.get("q") ?? "";
  const siteId = params.get("site") ? Number(params.get("site")) : null;
  const { data: sites } = useQuery({ queryKey: ["sites"], queryFn: api.sites });

  const query = useInfiniteQuery({
    queryKey: ["inspections", status, q, siteId],
    queryFn: ({ pageParam }) => api.inspections({ status, q, site_id: siteId, limit: PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const total = query.data?.pages[0]?.total ?? 0;

  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        title={`${total} inspection${total === 1 ? "" : "s"}`}
        subtitle="Every uploaded image with its per-worker verdict"
        actions={
          <>
            <select className="input w-auto rounded-full py-1.5" value={siteId ?? ""} onChange={(e) => set("site", e.target.value)}>
              <option value="">All sites</option>
              {sites?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <Segmented
              size="sm"
              value={status}
              onChange={(v) => set("status", v)}
              options={[
                { value: "", label: "All" },
                { value: "violation", label: "Violations" },
                { value: "unknown", label: "Needs review" },
                { value: "compliant", label: "Compliant" },
                { value: "empty", label: "No workers" },
              ]}
            />
          </>
        }
      />
      {q && (
        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
          Search: “{q}”
          <button onClick={() => set("q", "")}>
            <X size={14} />
          </button>
        </div>
      )}
      {query.isLoading && <Loading />}
      {query.error && <ErrorBox error={query.error} />}
      {!query.isLoading && items.length === 0 && (
        <Card>
          <EmptyState
            icon={<Images />}
            title="No inspections match"
            text="Upload images to start building the inspection history."
            action={
              <Link to="/upload" className="btn-primary">
                <Upload size={16} /> New inspection
              </Link>
            }
          />
        </Card>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {items.map((i) => (
          <Link key={i.id} to={`/inspections/${i.id}`} className="card group overflow-hidden transition hover:-translate-y-0.5 hover:shadow-float">
            <div className="relative aspect-[4/3] overflow-hidden bg-sunken dark:bg-sunken-dark">
              <img src={i.annotated_url} alt={i.filename} loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
              <StatusBadge status={i.status} className="absolute left-3 top-3 bg-white/90 shadow dark:bg-slate-900/85" />
              {i.owner && <span className="chip absolute right-3 top-3 max-w-[45%] truncate bg-slate-900/70 text-white">{i.owner}</span>}
            </div>
            <div className="space-y-1.5 p-4">
              <div className="truncate text-sm font-medium">{i.filename}</div>
              <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                <span className="inline-flex items-center gap-1">
                  <Users size={13} /> {i.num_persons}
                </span>
                {i.num_violations > 0 && <span className="text-red-500">{i.num_violations} violation{i.num_violations > 1 ? "s" : ""}</span>}
                {i.num_unknown > 0 && <span className="text-amber-600">{i.num_unknown} unknown</span>}
                <span className="ml-auto">{timeAgo(i.created_at)}</span>
              </div>
              <div className="truncate text-[11px] text-slate-400">
                #{i.id} · {i.site} · {Math.round(i.latency_ms)} ms
              </div>
            </div>
          </Link>
        ))}
      </div>
      {query.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <button className="btn-ghost" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
            {query.isFetchingNextPage ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
