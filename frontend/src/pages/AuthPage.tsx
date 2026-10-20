import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, HardHat, KeyRound, Lock, Mail, MailCheck, User as UserIcon } from "lucide-react";
import { useState, type FormEvent, type InputHTMLAttributes, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Spinner } from "../components/ui";
import { useMe } from "../lib/auth";

function Field({ icon, ...props }: { icon: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex items-center gap-3 rounded-2xl bg-sunken px-4 py-3 ring-1 ring-line focus-within:ring-2 focus-within:ring-brand-400 dark:bg-sunken-dark dark:ring-line-dark">
      <span className="text-slate-400">{icon}</span>
      <input {...props} className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400" />
    </label>
  );
}

function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="rounded-2xl bg-red-50 px-4 py-2.5 text-sm text-red-600 ring-1 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20">
      {error instanceof Error ? error.message : "Something went wrong"}
    </div>
  );
}

function SubmitButton({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <button type="submit" className="btn-primary w-full py-3 text-base" disabled={pending}>
      {pending && <Spinner className="h-4 w-4 text-white" />}
      {children}
    </button>
  );
}

/** Full-screen two-column layout shared by every auth page; exactly one viewport tall on desktop. */
function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-[100dvh] grid-cols-1 bg-canvas lg:h-[100dvh] lg:grid-cols-2 lg:overflow-hidden dark:bg-canvas-dark">
      <div className="relative hidden min-h-0 flex-col overflow-hidden bg-gradient-to-br from-brand-500 via-brand-700 to-brand-900 px-12 pt-10 text-white lg:flex">
        <div className="pointer-events-none absolute -right-24 top-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
        <Link to="/" className="flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 ring-1 ring-white/20">
            <HardHat size={20} />
          </span>
          <span className="text-lg font-semibold">SafeSight</span>
        </Link>
        <div className="mt-[6vh] max-w-md">
          <h2 className="text-[clamp(1.8rem,3.2vw,2.6rem)] font-semibold leading-tight tracking-tight">Know who is missing PPE, worker by worker.</h2>
          <ul className="mt-6 space-y-2.5 text-white/85">
            {["Per-worker helmet, vest, gloves & more", "Review queue for every violation", "PDF & CSV reports per site", "Your photos are visible only to you"].map((t) => (
              <li key={t} className="flex items-center gap-2.5">
                <CheckCircle2 size={18} className="shrink-0 text-brand-200" /> {t}
              </li>
            ))}
          </ul>
        </div>
        {/* Fills the remaining height and is clipped at the bottom, so the page never scrolls. */}
        <div className="relative mt-8 min-h-0 flex-1">
          <div className="absolute inset-x-0 top-0 bottom-0 overflow-hidden rounded-t-2xl bg-white/10 p-2 pb-0 ring-1 ring-white/20">
            <img src="/preview-dashboard.jpg" alt="" className="w-full rounded-t-xl object-cover object-left-top opacity-95" />
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-col px-5 py-6 sm:px-10 lg:overflow-y-auto">
        <Link to="/" className="inline-flex items-center gap-1.5 self-start text-sm text-slate-500 hover:text-slate-800 dark:hover:text-white">
          <ArrowLeft size={16} /> Home
        </Link>
        <div className="mx-auto my-auto w-full max-w-sm py-8">{children}</div>
      </div>
    </div>
  );
}

function Heading({ icon, title, text }: { icon?: ReactNode; title: string; text: string }) {
  return (
    <>
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-glow lg:hidden">
        {icon ?? <HardHat size={22} />}
      </div>
      <h1 className="mt-6 text-3xl font-semibold tracking-tight lg:mt-0">{title}</h1>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{text}</p>
    </>
  );
}

function useNext() {
  const [params] = useSearchParams();
  const next = params.get("next") || "/dashboard";
  return { raw: params.get("next"), safe: next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard" };
}

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const next = useNext();
  const { user, isLoading } = useMe();
  const { data: cfg } = useQuery({ queryKey: ["auth-config"], queryFn: api.authConfig });
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const isLogin = mode === "login";

  const submit = useMutation({
    mutationFn: () => (isLogin ? api.login(email, password) : api.register(name, email, password)),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      nav(next.safe, { replace: true });
    },
  });

  if (!isLoading && user) return <Navigate to={next.safe} replace />;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit.mutate();
  };

  return (
    <AuthShell>
      <Heading
        title={isLogin ? "Welcome back" : "Create your account"}
        text={isLogin ? "Log in to see your inspections and incidents." : "Start checking site photos for PPE in a minute."}
      />
      {!isLogin && cfg?.first_user && (
        <div className="mt-4 rounded-2xl bg-brand-50 px-4 py-3 text-xs text-brand-800 ring-1 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-200 dark:ring-brand-500/20">
          You are the first user, so this account will be the <b>admin</b> (manages models and site policies).
        </div>
      )}
      {!isLogin && cfg && !cfg.signup_enabled && (
        <div className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-xs text-amber-800 ring-1 ring-amber-100">
          Sign-up is turned off on this server. Ask your admin for an account.
        </div>
      )}

      <form onSubmit={onSubmit} className="mt-7 space-y-3">
        {!isLogin && (
          <Field icon={<UserIcon size={17} />} placeholder="Full name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required />
        )}
        <Field icon={<Mail size={17} />} type="email" placeholder="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Field
          icon={<Lock size={17} />}
          type="password"
          placeholder={isLogin ? "Password" : "Password (min. 8 characters)"}
          autoComplete={isLogin ? "current-password" : "new-password"}
          minLength={isLogin ? undefined : 8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {isLogin && (
          <div className="flex justify-end">
            <Link
              to={`/forgot-password${email ? `?email=${encodeURIComponent(email)}` : ""}`}
              className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300"
            >
              Forgot password?
            </Link>
          </div>
        )}
        <ErrorNote error={submit.error} />
        <SubmitButton pending={submit.isPending}>{isLogin ? "Log in" : "Create account"}</SubmitButton>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        {isLogin ? "New to SafeSight? " : "Already have an account? "}
        <Link
          to={`${isLogin ? "/register" : "/login"}${next.raw ? `?next=${encodeURIComponent(next.raw)}` : ""}`}
          className="font-medium text-brand-700 hover:underline dark:text-brand-300"
        >
          {isLogin ? "Create an account" : "Log in"}
        </Link>
      </p>
    </AuthShell>
  );
}

export function ForgotPasswordPage() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const { data: cfg } = useQuery({ queryKey: ["auth-config"], queryFn: api.authConfig });
  const send = useMutation({ mutationFn: () => api.forgotPassword(email) });

  if (send.isSuccess) {
    return (
      <AuthShell>
        <Heading icon={<MailCheck size={22} />} title="Check your email" text={`If an account exists for ${email}, we've sent a link to reset the password.`} />
        <div className="mt-6 space-y-2 rounded-2xl bg-sunken p-4 text-sm text-slate-600 ring-1 ring-line dark:bg-sunken-dark dark:text-slate-300 dark:ring-line-dark">
          <p>The link works once and expires in 30 minutes. Check your spam folder if it doesn't arrive.</p>
          {cfg && !cfg.email_enabled && (
            <p className="text-amber-700 dark:text-amber-300">
              Email isn't set up on this server yet, so the link is printed in the server log. Ask your admin.
            </p>
          )}
        </div>
        <button className="btn-ghost mt-4 w-full" onClick={() => send.reset()}>
          Use a different email
        </button>
        <p className="mt-6 text-center text-sm text-slate-500">
          Remembered it?{" "}
          <Link to="/login" className="font-medium text-brand-700 hover:underline dark:text-brand-300">
            Back to log in
          </Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <Heading icon={<KeyRound size={22} />} title="Forgot your password?" text="Enter your account email and we'll send you a link to choose a new one." />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send.mutate();
        }}
        className="mt-7 space-y-3"
      >
        <Field icon={<Mail size={17} />} type="email" placeholder="Email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        <ErrorNote error={send.error} />
        <SubmitButton pending={send.isPending}>Send reset link</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        <Link to="/login" className="font-medium text-brand-700 hover:underline dark:text-brand-300">
          Back to log in
        </Link>
      </p>
    </AuthShell>
  );
}

export function ResetPasswordPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const check = useQuery({ queryKey: ["reset-check", token], queryFn: () => api.checkReset(token), enabled: !!token, retry: false });
  const reset = useMutation({
    mutationFn: () => api.resetPassword(token, password),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      nav("/dashboard", { replace: true });
    },
  });

  if (!token || check.data?.valid === false) {
    return (
      <AuthShell>
        <Heading icon={<KeyRound size={22} />} title="Link expired" text="This reset link is invalid, already used, or older than 30 minutes." />
        <Link to="/forgot-password" className="btn-primary mt-7 w-full py-3 text-base">
          Request a new link
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <Heading icon={<KeyRound size={22} />} title="Choose a new password" text="You'll be logged in, and any other open sessions will be signed out." />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (password !== confirm) {
            setMismatch(true);
            return;
          }
          setMismatch(false);
          reset.mutate();
        }}
        className="mt-7 space-y-3"
      >
        <Field icon={<Lock size={17} />} type="password" placeholder="New password (min. 8 characters)" autoComplete="new-password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
        <Field icon={<Lock size={17} />} type="password" placeholder="Repeat new password" autoComplete="new-password" minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        {mismatch && <ErrorNote error={new Error("The two passwords don't match")} />}
        <ErrorNote error={reset.error} />
        <SubmitButton pending={reset.isPending || check.isLoading}>Save new password</SubmitButton>
      </form>
    </AuthShell>
  );
}
