import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { Loading } from "../components/ui";

export function useMe() {
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 60_000, retry: false });
  return { user: data ?? null, isLoading, isAdmin: data?.role === "admin" };
}

export function useLogout() {
  const qc = useQueryClient();
  const nav = useNavigate();
  return async () => {
    await api.logout().catch(() => undefined);
    qc.clear();
    nav("/", { replace: true });
  };
}

/** Renders children only for signed-in users; everyone else is sent to /login?next=… */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, isLoading } = useMe();
  const loc = useLocation();
  if (isLoading) return <Loading label="Checking your session…" />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin, isLoading } = useMe();
  if (isLoading) return <Loading />;
  if (!isAdmin) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
