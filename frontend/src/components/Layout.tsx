import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Bell,
  Boxes,
  Camera,
  MoreHorizontal,
  ClipboardCheck,
  Download,
  FileBarChart2,
  HardHat,
  Images,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  PanelLeft,
  Search,
  Settings2,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useLogout, useMe } from "../lib/auth";

const MAIN = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/inspections", label: "Inspections", icon: Images },
  { to: "/review", label: "Review Queue", icon: ClipboardCheck, badge: "review" as const },
  { to: "/reports", label: "Reports", icon: FileBarChart2 },
];
const TOOLS = [
  { to: "/upload", label: "New Inspection", icon: Upload },
  { to: "/models", label: "Models", icon: Boxes, admin: true },
  { to: "/sites", label: "Sites & Policies", icon: HardHat },
];
const OTHERS = [{ to: "/system", label: "System", icon: Settings2 }];

const TITLES: [RegExp, string][] = [
  [/^\/dashboard/, "Dashboard"],
  [/^\/inspections\/\d+/, "Inspection"],
  [/^\/inspections/, "Inspections"],
  [/^\/review/, "Review Queue"],
  [/^\/reports/, "Reports"],
  [/^\/upload/, "New Inspection"],
  [/^\/models/, "Models"],
  [/^\/sites/, "Sites & Policies"],
  [/^\/system/, "System"],
];

function useDarkMode() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
  }, [dark]);
  return [dark, setDark] as const;
}

function Logo({ compact }: { compact?: boolean }) {
  return (
    <NavLink to="/" className="flex items-center gap-3" title="SafeSight home">
      <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow">
        <HardHat size={20} strokeWidth={2.2} />
      </div>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[17px] font-semibold tracking-tight">SafeSight</div>
          <div className="text-[11px] text-slate-400">PPE compliance</div>
        </div>
      )}
    </NavLink>
  );
}

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  count,
  collapsed,
  onClick,
}: {
  to: string;
  label: string;
  icon: typeof Upload;
  end?: boolean;
  count?: number;
  collapsed?: boolean;
  onClick?: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        clsx(
          "group relative flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition",
          collapsed && "justify-center",
          isActive
            ? "bg-panel font-medium text-slate-900 shadow-card dark:bg-panel-dark dark:text-white"
            : "text-slate-500 hover:bg-white/60 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-slate-200",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="pointer-events-none absolute inset-y-1 right-0 w-16 rounded-r-2xl bg-gradient-to-l from-brand-300/40 via-brand-200/10 to-transparent blur-[2px] dark:from-brand-500/25" />
          )}
          <Icon size={18} className={clsx(isActive && "text-brand-600 dark:text-brand-400")} />
          {!collapsed && <span className="flex-1">{label}</span>}
          {!collapsed && count !== undefined && count > 0 && (
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-semibold text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
              {count}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

function Sidebar({ collapsed, onToggle, onNavigate }: { collapsed: boolean; onToggle?: () => void; onNavigate?: () => void }) {
  const [dark, setDark] = useDarkMode();
  const { user, isAdmin } = useMe();
  const logout = useLogout();
  const initials = (user?.name || user?.email || "?")
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
  const { data } = useQuery({
    queryKey: ["incident-counts"],
    queryFn: () => api.incidents({ status: "open", limit: 1 }),
    refetchInterval: 30_000,
  });
  const open = data?.total;
  const section = (title: string, items: typeof TOOLS) => (
    <div className="space-y-1">
      {!collapsed && <div className="label-caps mb-2 px-3">{title}</div>}
      {items.filter((it) => !("admin" in it && it.admin) || isAdmin).map((it) => (
        <NavItem
          key={it.to}
          {...it}
          collapsed={collapsed}
          onClick={onNavigate}
          count={"badge" in it && it.badge === "review" ? open : undefined}
        />
      ))}
    </div>
  );
  return (
    <aside className={clsx("flex h-full flex-col gap-7 py-6", collapsed ? "w-[84px] px-3" : "w-[252px] px-4")}>
      <div className={clsx("flex items-center", collapsed ? "justify-center" : "justify-between pl-1")}>
        <Logo compact={collapsed} />
        {onToggle && !collapsed && (
          <button onClick={onToggle} className="rounded-lg p-1.5 text-slate-400 hover:bg-white/70 dark:hover:bg-white/5" title="Collapse sidebar">
            <PanelLeft size={18} />
          </button>
        )}
      </div>
      {collapsed && onToggle && (
        <button onClick={onToggle} className="mx-auto -mt-3 rounded-lg p-1.5 text-slate-400 hover:bg-white/70 dark:hover:bg-white/5" title="Expand sidebar">
          <PanelLeft size={18} />
        </button>
      )}
      <div className="h-px bg-line dark:bg-line-dark" />
      <nav className="flex flex-1 flex-col gap-7 overflow-y-auto scrollbar-thin">
        {section("Main menu", MAIN)}
        {section("Tools", TOOLS)}
        <div className="mt-auto space-y-1">
          {!collapsed && <div className="label-caps mb-2 px-3">Others</div>}
          {OTHERS.map((it) => (
            <NavItem key={it.to} {...it} collapsed={collapsed} onClick={onNavigate} />
          ))}
          <button
            onClick={() => setDark(!dark)}
            className={clsx(
              "flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-slate-500 hover:bg-white/60 dark:text-slate-400 dark:hover:bg-white/5",
              collapsed && "justify-center",
            )}
            title="Toggle dark mode"
          >
            <Moon size={18} />
            {!collapsed && <span className="flex-1 text-left">Dark mode</span>}
            {!collapsed && (
              <span className={clsx("relative h-5 w-9 rounded-full transition", dark ? "bg-brand-500" : "bg-slate-200 dark:bg-slate-700")}>
                <span className={clsx("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all", dark ? "left-[18px]" : "left-0.5")} />
              </span>
            )}
          </button>
        </div>
      </nav>
      <div className={clsx("flex items-center gap-3 rounded-2xl", !collapsed && "bg-white/60 p-2.5 dark:bg-white/5")}>
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-xs font-semibold text-white">
          {initials}
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-medium">{user?.name || "Signed in"}</div>
            <div className="truncate text-[11px] text-slate-400">
              {user?.email}
              {isAdmin && " · admin"}
            </div>
          </div>
        )}
        {!collapsed && (
          <button onClick={logout} className="rounded-lg p-1.5 text-slate-400 hover:bg-white hover:text-red-500 dark:hover:bg-white/10" title="Log out">
            <LogOut size={16} />
          </button>
        )}
      </div>
    </aside>
  );
}

function SearchBox() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        nav(`/inspections?q=${encodeURIComponent(q.trim())}`);
      }}
      className="hidden items-center gap-2 rounded-full bg-panel px-4 py-2 shadow-card ring-1 ring-black/[0.03] md:flex dark:bg-panel-dark"
    >
      <Search size={16} className="text-slate-400" />
      <input
        ref={ref}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search inspections"
        className="w-40 bg-transparent text-sm outline-none placeholder:text-slate-400 lg:w-52"
      />
      <kbd className="rounded-md bg-sunken px-1.5 py-0.5 text-[10px] text-slate-400 ring-1 ring-line dark:bg-sunken-dark dark:ring-line-dark">Ctrl K</kbd>
    </form>
  );
}

function BottomNav({ openCount, onMore }: { openCount?: number; onMore: () => void }) {
  const item = (to: string, label: string, Icon: typeof Upload, end?: boolean, badge?: number) => (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        clsx(
          "relative flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium",
          isActive ? "text-brand-700 dark:text-brand-300" : "text-slate-400",
        )
      }
    >
      <Icon size={20} />
      {label}
      {!!badge && (
        <span className="absolute right-[22%] top-1 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[9px] font-semibold text-white">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </NavLink>
  );
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/90 backdrop-blur-xl lg:hidden dark:border-line-dark dark:bg-[#0c1420]/90"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="mx-auto flex max-w-lg items-end px-2">
        {item("/dashboard", "Home", LayoutDashboard, true)}
        {item("/inspections", "Inspections", Images)}
        <NavLink to="/upload" className="-mt-5 flex flex-1 flex-col items-center gap-0.5 pb-2 text-[10px] font-medium text-brand-700 dark:text-brand-300">
          <span className="grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow ring-4 ring-white dark:ring-[#0c1420]">
            <Camera size={24} />
          </span>
          Inspect
        </NavLink>
        {item("/review", "Review", ClipboardCheck, false, openCount)}
        <button onClick={onMore} className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium text-slate-400">
          <MoreHorizontal size={20} />
          More
        </button>
      </div>
    </nav>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const nav = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const title = TITLES.find(([re]) => re.test(loc.pathname))?.[1] ?? "SafeSight";
  const { data: openReview } = useQuery({
    queryKey: ["incident-counts"],
    queryFn: () => api.incidents({ status: "open", limit: 1 }),
  });
  useEffect(() => setDrawer(false), [loc.pathname]);

  return (
    <div className="min-h-screen bg-canvas p-0 lg:p-4 dark:bg-canvas-dark">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-[1600px] overflow-hidden bg-[#f8f9fb] lg:rounded-[28px] lg:shadow-card lg:ring-1 lg:ring-black/[0.04] dark:bg-[#0c1420] dark:lg:ring-white/[0.05]">
        <div className="sticky top-0 hidden h-[calc(100vh-2rem)] shrink-0 lg:block">
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </div>

        {drawer && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={() => setDrawer(false)} />
            <div className="absolute inset-y-0 left-0 bg-[#f8f9fb] shadow-float dark:bg-[#0c1420]">
              <button className="absolute right-3 top-6 rounded-lg p-1.5 text-slate-400" onClick={() => setDrawer(false)}>
                <X size={18} />
              </button>
              <Sidebar collapsed={false} onNavigate={() => setDrawer(false)} />
            </div>
          </div>
        )}

        <main className="min-w-0 flex-1 px-4 pb-28 pt-4 sm:px-6 lg:pb-10 lg:pt-6">
          <header className="mb-5 flex items-center gap-3 lg:mb-6">
            <button className="hidden rounded-xl p-2 text-slate-500 ring-1 ring-line sm:block lg:hidden dark:ring-line-dark" onClick={() => setDrawer(true)}>
              <Menu size={18} />
            </button>
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow sm:hidden">
              <HardHat size={18} />
            </div>
            <h1 className="flex-1 truncate text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
            <SearchBox />
            <a href={api.reportUrl("pdf", {})} className="btn-primary hidden sm:inline-flex" title="Download a PDF report for the last 30 days">
              <Download size={16} /> Export
            </a>
            <button
              onClick={() => nav("/review")}
              className="relative grid h-10 w-10 place-items-center rounded-full bg-panel shadow-card ring-1 ring-black/[0.03] dark:bg-panel-dark"
              title="Open incidents"
            >
              <Bell size={17} />
              {!!openReview?.total && (
                <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[9px] font-semibold text-white">
                  {openReview.total > 99 ? "99+" : openReview.total}
                </span>
              )}
            </button>
            <button
              onClick={() => nav("/upload")}
              className="relative hidden items-center gap-2 rounded-full bg-panel px-4 py-2 text-sm font-medium shadow-card ring-1 ring-black/[0.03] sm:inline-flex dark:bg-panel-dark"
            >
              <span className="pointer-events-none absolute inset-y-0 right-0 w-12 rounded-r-full bg-gradient-to-l from-brand-300/50 to-transparent" />
              <Sparkles size={16} className="text-brand-600" /> Inspect
            </button>
          </header>
          {children}
        </main>
      </div>
      <BottomNav openCount={openReview?.total} onMore={() => setDrawer(true)} />
    </div>
  );
}
