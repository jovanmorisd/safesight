import clsx from "clsx";
import {
  ArrowRight,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Eye,
  FileBarChart2,
  HardHat,
  Layers,
  Menu,
  ScanLine,
  ShieldCheck,
  Smartphone,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMe } from "../lib/auth";

const FEATURES = [
  {
    icon: Users,
    title: "Checks every worker",
    text: "Pose estimation finds each person's head, torso, hands and feet. A helmet only counts if it is on that worker's head.",
  },
  {
    icon: Eye,
    title: "Honest about what it can't see",
    text: "Back turned or hidden? The worker is marked unknown, never a false violation, and goes to the review queue.",
  },
  {
    icon: ClipboardCheck,
    title: "Review queue",
    text: "Confirm real violations or mark false alarms in one tap. Every decision is logged against the reviewer.",
  },
  {
    icon: FileBarChart2,
    title: "Dashboards & reports",
    text: "Compliance trends per site and per PPE item, with PDF summaries (including evidence crops) and CSV logs.",
  },
  {
    icon: HardHat,
    title: "Site policies",
    text: "Each site decides what is mandatory: helmets, hi-vis vests, gloves, boots, goggles, masks or ear protection.",
  },
  {
    icon: Smartphone,
    title: "Works on your phone",
    text: "Open it on site, tap the camera button, and get a verdict for every worker in the photo within seconds.",
  },
];

const STEPS = [
  { icon: Camera, title: "Snap or upload", text: "Take a photo on site or upload images from a camera." },
  { icon: ScanLine, title: "AI checks each worker", text: "PPE detection and pose estimation match equipment to people." },
  { icon: ShieldCheck, title: "Review & report", text: "Violations become incidents you can review and export." },
];

const PPE = ["Helmet", "Hi-vis vest", "Gloves", "Safety boots", "Goggles", "Mask", "Ear protection"];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow">
        <HardHat size={18} />
      </span>
      <span className="text-lg font-semibold tracking-tight">SafeSight</span>
    </Link>
  );
}

export default function Landing() {
  const { user } = useMe();
  const [menu, setMenu] = useState(false);
  const cta = user ? { to: "/dashboard", label: "Open dashboard" } : { to: "/register", label: "Get started" };
  const links = [
    { href: "#features", label: "Features" },
    { href: "#how", label: "How it works" },
    { href: "#ppe", label: "PPE covered" },
  ];

  return (
    <div className="min-h-screen bg-canvas text-slate-900 dark:bg-canvas-dark dark:text-slate-100">
      {/* Nav */}
      <header className="sticky top-0 z-30 border-b border-transparent bg-canvas/80 backdrop-blur-xl dark:bg-canvas-dark/80">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Logo />
          <nav className="hidden items-center gap-7 text-sm text-slate-600 md:flex dark:text-slate-300">
            {links.map((l) => (
              <a key={l.href} href={l.href} className="hover:text-slate-900 dark:hover:text-white">
                {l.label}
              </a>
            ))}
          </nav>
          <div className="hidden items-center gap-2 md:flex">
            {!user && (
              <Link to="/login" className="btn-ghost">
                Log in
              </Link>
            )}
            <Link to={cta.to} className="btn bg-slate-900 text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900">
              {cta.label}
            </Link>
          </div>
          <button className="rounded-xl p-2 ring-1 ring-line md:hidden dark:ring-line-dark" onClick={() => setMenu(!menu)} aria-label="Menu">
            {menu ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
        {menu && (
          <div className="space-y-1 border-t border-line px-4 pb-4 pt-2 md:hidden dark:border-line-dark">
            {links.map((l) => (
              <a key={l.href} href={l.href} onClick={() => setMenu(false)} className="block rounded-xl px-3 py-2 text-sm hover:bg-white/70 dark:hover:bg-white/5">
                {l.label}
              </a>
            ))}
            <div className="grid grid-cols-2 gap-2 pt-2">
              {!user && (
                <Link to="/login" className="btn-ghost">
                  Log in
                </Link>
              )}
              <Link to={cta.to} className={clsx("btn-primary", user && "col-span-2")}>
                {cta.label}
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-[radial-gradient(ellipse_at_top,rgba(45,212,191,.22),transparent_60%)]" />
        <div className="relative mx-auto max-w-6xl px-4 pb-10 pt-14 text-center sm:px-6 sm:pt-20">
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-card ring-1 ring-black/[0.04] dark:bg-panel-dark dark:text-slate-300">
            <span className="rounded-full bg-brand-500 px-2 py-0.5 text-[10px] font-semibold text-white">AI</span>
            Computer-vision PPE compliance
          </span>
          <h1 className="mx-auto mt-6 max-w-4xl text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
            Every worker. Every helmet.
            <br />
            <span className="bg-gradient-to-r from-brand-500 to-brand-700 bg-clip-text text-transparent">Checked in seconds.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-slate-500 sm:text-lg dark:text-slate-400">
            SafeSight looks at a construction-site photo and tells you, worker by worker, who is missing a helmet, vest or other required PPE.
            Then it helps you review and report it.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link to={cta.to} className="btn-primary px-6 py-3 text-base">
              {cta.label} <ArrowRight size={18} />
            </Link>
            {!user && (
              <Link to="/login" className="btn-ghost px-6 py-3 text-base">
                I have an account
              </Link>
            )}
          </div>

          <div className="relative mx-auto mt-14 max-w-5xl">
            <div className="absolute -inset-x-6 -bottom-6 top-10 rounded-[40px] bg-gradient-to-b from-brand-200/40 to-transparent blur-2xl dark:from-brand-500/10" />
            <div className="relative overflow-hidden rounded-[24px] bg-white p-2 shadow-float ring-1 ring-black/[0.06] sm:rounded-[32px] sm:p-3 dark:bg-panel-dark dark:ring-white/10">
              <img src="/preview-dashboard.jpg" alt="SafeSight dashboard" className="w-full rounded-[18px] sm:rounded-[24px]" />
            </div>
          </div>
        </div>
      </section>

      {/* Stats strip */}
      <section className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid grid-cols-2 gap-3 rounded-3xl bg-white p-4 shadow-card ring-1 ring-black/[0.03] sm:grid-cols-4 sm:p-6 dark:bg-panel-dark">
          {[
            ["7", "PPE types checked"],
            ["Per worker", "verdicts, not per image"],
            ["~1 s", "per photo, no GPU needed"],
            ["0", "installs: works in the browser"],
          ].map(([v, l]) => (
            <div key={l} className="rounded-2xl p-3 text-center">
              <div className="text-2xl font-semibold tracking-tight text-brand-700 dark:text-brand-300">{v}</div>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20 sm:px-6">
        <div className="text-center">
          <span className="chip bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">Features</span>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">More than “is there a helmet?”</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500 dark:text-slate-400">
            Detecting PPE is easy. Knowing whether <i>this</i> worker is wearing it is the hard part, and that is what SafeSight does.
          </p>
        </div>
        <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-6 transition hover:-translate-y-0.5 hover:shadow-float">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                <f.icon size={20} />
              </div>
              <div className="mt-4 text-base font-semibold">{f.title}</div>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-500 dark:text-slate-400">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-24 bg-white py-20 dark:bg-panel-dark/60">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="text-center">
            <span className="chip bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">How it works</span>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Three steps, one photo</h2>
          </div>
          <div className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div key={s.title} className="relative rounded-3xl bg-sunken p-6 dark:bg-sunken-dark">
                <span className="absolute right-5 top-5 text-5xl font-semibold text-brand-100 dark:text-brand-500/15">{i + 1}</span>
                <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow">
                  <s.icon size={20} />
                </div>
                <div className="mt-4 text-base font-semibold">{s.title}</div>
                <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PPE covered */}
      <section id="ppe" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20 sm:px-6">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-2">
          <div>
            <span className="chip bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">PPE covered</span>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">From helmets to ear protection</h2>
            <p className="mt-3 text-slate-500 dark:text-slate-400">
              Choose what each site requires. Items the current model cannot detect are clearly marked <b>not checked</b>, so a missing
              capability never turns into a false violation.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {["Worn, missing, unknown or not checked, for every item", "Your data stays in your account", "Photos auto-delete after 30 days"].map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <CheckCircle2 size={18} className="text-brand-600" /> {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="card flex flex-wrap gap-2.5 p-6">
            {PPE.map((p) => (
              <span key={p} className="inline-flex items-center gap-2 rounded-2xl bg-sunken px-4 py-3 text-sm font-medium ring-1 ring-line dark:bg-sunken-dark dark:ring-line-dark">
                <span className="h-2 w-2 rounded-full bg-brand-500" /> {p}
              </span>
            ))}
            <div className="mt-2 flex w-full items-center gap-2 rounded-2xl bg-brand-50 px-4 py-3 text-xs text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
              <Layers size={16} /> Bring your own trained model: upload weights and switch with one click.
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        <div className="relative overflow-hidden rounded-[32px] bg-gradient-to-br from-brand-500 to-brand-800 px-6 py-12 text-center text-white shadow-glow sm:px-12">
          <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/10 blur-2xl" />
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Run your first inspection today</h2>
          <p className="mx-auto mt-3 max-w-xl text-white/80">Create an account, upload a site photo and see every worker's PPE status in seconds.</p>
          <Link to={cta.to} className="btn mt-7 bg-white px-6 py-3 text-base text-brand-800 hover:bg-brand-50">
            {cta.label} <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="overflow-hidden border-t border-line dark:border-line-dark">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-slate-500 sm:px-6">
          <Logo />
          <span>Computer Vision project · decision support, every incident is reviewed by a person.</span>
        </div>
        <div className="pointer-events-none select-none text-center text-[22vw] font-semibold leading-[0.8] tracking-tighter text-slate-200/70 dark:text-white/[0.04]">
          SafeSight
        </div>
      </footer>
    </div>
  );
}
