// Typed client for the FastAPI backend (same origin; Vite proxies /api and /media in dev).

export type ItemState = "worn" | "absent" | "unknown" | "not_checked";
export type Overall = "compliant" | "violation" | "unknown";
export type InspectionStatus = Overall | "empty";

export interface ItemInfo {
  state: ItemState;
  conf: number | null;
  reason: string;
  evidence: number[] | null;
}

export interface PersonOut {
  id: number;
  idx: number;
  box: number[];
  conf: number;
  has_pose: boolean;
  overall: Overall;
  missing: string[];
  uncertain: string[];
  items: Record<string, ItemInfo>;
  crop_url: string;
}

export interface InspectionSummary {
  id: number;
  filename: string;
  site_id: number | null;
  site: string;
  owner: string | null;
  created_at: string;
  status: InspectionStatus;
  num_persons: number;
  num_violations: number;
  num_unknown: number;
  num_compliant: number;
  latency_ms: number;
  model_label: string;
  image_url: string;
  annotated_url: string;
  width: number;
  height: number;
}

export interface Incident {
  id: number;
  inspection_id: number;
  person_id: number;
  site_id: number | null;
  site: string;
  kind: "violation" | "review";
  items: string[];
  severity: "low" | "medium" | "high";
  status: "open" | "confirmed" | "false_positive" | "resolved";
  reviewer: string;
  notes: string;
  created_at: string;
  reviewed_at: string | null;
  person: PersonOut | null;
}

export interface InspectionDetail extends InspectionSummary {
  required: string[];
  supported: string[];
  timings: Record<string, number>;
  persons: PersonOut[];
  detections: { cls: string; raw_cls: string; conf: number; box: number[]; source: string }[];
  incidents: Incident[];
}

export interface SeriesPoint {
  key: string;
  violations: number;
  compliant: number;
  unknown: number;
  rate: number | null;
}

export interface Stats {
  days: number;
  kpis: {
    compliance_rate: number | null;
    compliance_delta: number | null;
    open_incidents: number;
    incidents_opened: number;
    incidents_delta: number;
    unknown_rate: number | null;
    unknown_delta: number | null;
    inspections: number;
    persons: number;
    violations: number;
    compliant: number;
    unknown: number;
    review_precision: number | null;
    reviewed: number;
    avg_latency_ms: number | null;
  };
  per_item: Record<string, { worn: number; absent: number; unknown: number; not_checked: number }>;
  daily: SeriesPoint[];
  monthly: SeriesPoint[];
  by_model: { model: string; compliance_rate: number | null; inspections: number }[];
  latest: InspectionSummary | null;
}

export interface Site {
  id: number;
  name: string;
  location: string;
  required_ppe: string[];
  inspections: number;
  created_at: string;
}

export interface ModelVersion {
  id: number;
  name: string;
  weights_path: string;
  sha256: string;
  conf: number;
  imgsz: number;
  class_map: Record<string, string> | null;
  classes: string[];
  supported: string[];
  is_active: boolean;
  notes: string;
  created_at: string;
}

export interface Meta {
  database: string;
  storage: string;
  retention_days: number;
  ppe_items: string[];
  pipeline: {
    device: string;
    runtime?: string;
    pose: string | null;
    supported: string[];
    detectors: { name: string; weights: string; classes: string[]; class_map: Record<string, string> }[];
  };
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: "admin" | "user";
  created_at: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", ...init });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    // session expired or missing: go to the login page and come back afterwards
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    if (!window.location.pathname.startsWith("/login")) window.location.assign(`/login?next=${next}`);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const qs = (params: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  });
  const str = s.toString();
  return str ? `?${str}` : "";
};

export const api = {
  me: async (): Promise<User | null> => {
    try {
      return await request<User>("/api/auth/me");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return null;
      throw e;
    }
  },
  authConfig: () => request<{ signup_enabled: boolean; first_user: boolean; email_enabled: boolean }>("/api/auth/config"),
  forgotPassword: (email: string) => request<{ ok: boolean }>("/api/auth/forgot", json("POST", { email })),
  checkReset: (token: string) => request<{ valid: boolean }>(`/api/auth/reset/check?token=${encodeURIComponent(token)}`),
  resetPassword: (token: string, password: string) => request<User>("/api/auth/reset", json("POST", { token, password })),
  login: (email: string, password: string) => request<User>("/api/auth/login", json("POST", { email, password })),
  register: (name: string, email: string, password: string) =>
    request<User>("/api/auth/register", json("POST", { name, email, password })),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  meta: () => request<Meta>("/api/meta"),
  stats: (days: number, siteId?: number | null) => request<Stats>(`/api/stats${qs({ days, site_id: siteId })}`),

  inspections: (p: { status?: string; site_id?: number | null; q?: string; limit?: number; offset?: number }) =>
    request<{ total: number; items: InspectionSummary[] }>(`/api/inspections${qs(p)}`),
  inspection: (id: number) => request<InspectionDetail>(`/api/inspections/${id}`),
  deleteInspection: (id: number) => request<{ deleted: number }>(`/api/inspections/${id}`, { method: "DELETE" }),
  upload: (files: File[], siteId: number | null) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (siteId) fd.append("site_id", String(siteId));
    return request<{ inspections: InspectionSummary[]; errors: string[] }>("/api/inspections", {
      method: "POST",
      body: fd,
    });
  },

  incidents: (p: { status?: string; kind?: string; site_id?: number | null; limit?: number }) =>
    request<{ total: number; counts: Record<string, number>; items: Incident[] }>(`/api/incidents${qs(p)}`),
  updateIncident: (id: number, body: Partial<Pick<Incident, "status" | "notes">>) =>
    request<Incident>(`/api/incidents/${id}`, json("PATCH", body)),

  sites: () => request<Site[]>("/api/sites"),
  createSite: (body: { name: string; location: string; required_ppe: string[] }) =>
    request<Site>("/api/sites", json("POST", body)),
  updateSite: (id: number, body: { name: string; location: string; required_ppe: string[] }) =>
    request<Site>(`/api/sites/${id}`, json("PUT", body)),

  models: () => request<ModelVersion[]>("/api/models"),
  modelUploadUrl: (name: string) =>
    request<{ key: string; url: string; method: "PUT" }>("/api/models/upload-url", json("POST", { name })),
  registerModel: (body: { name: string; key: string; conf: number; class_map?: Record<string, string> | null; notes: string }) =>
    request<ModelVersion>("/api/models", json("POST", body)),
  updateModel: (
    id: number,
    body: { is_active?: boolean; exclusive?: boolean; conf?: number; class_map?: Record<string, string>; notes?: string },
  ) => request<ModelVersion>(`/api/models/${id}`, json("PATCH", body)),
  deleteModel: (id: number) => request<{ deleted: number }>(`/api/models/${id}`, { method: "DELETE" }),

  reportUrl: (kind: "pdf" | "csv", p: { start?: string; end?: string; site_id?: number | null }) =>
    `/api/reports/${kind === "pdf" ? "summary.pdf" : "incidents.csv"}${qs(p)}`,
};
