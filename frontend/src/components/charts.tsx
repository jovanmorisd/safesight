import clsx from "clsx";
import { useId, useMemo, useState } from "react";

const toXY = (cx: number, cy: number, r: number, deg: number) => {
  const a = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)] as const;
};

function arcPath(cx: number, cy: number, r: number, from: number, to: number) {
  const [x1, y1] = toXY(cx, cy, r, from);
  const [x2, y2] = toXY(cx, cy, r, to);
  const large = Math.abs(from - to) > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`; // clockwise on screen
}

/** Open arc gauge with a handle dot, as used on the KPI cards. `value` is 0..100. */
export function ArcGauge({
  value,
  tone = "brand",
  size = 120,
}: {
  value: number | null;
  tone?: "brand" | "bad" | "warn";
  size?: number;
}) {
  const id = useId();
  const v = Math.max(0, Math.min(100, value ?? 0)) / 100;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 10;
  const start = 210;
  const span = 240;
  const end = start - span * v;
  const [hx, hy] = toXY(cx, cy, r, end);
  const colors = {
    brand: ["#0f766e", "#2dd4bf"],
    bad: ["#b91c1c", "#f87171"],
    warn: ["#b45309", "#fbbf24"],
  }[tone];
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor={colors[0]} />
          <stop offset="1" stopColor={colors[1]} />
        </linearGradient>
      </defs>
      <path d={arcPath(cx, cy, r, start, start - span)} stroke="currentColor" className="text-slate-200 dark:text-slate-700" strokeWidth={9} fill="none" strokeLinecap="round" />
      {v > 0.005 && (
        <path d={arcPath(cx, cy, r, start, end)} stroke={`url(#g${id})`} strokeWidth={9} fill="none" strokeLinecap="round" />
      )}
      {value !== null && (
        <circle cx={hx} cy={hy} r={7} fill="white" stroke={colors[0]} strokeWidth={4} className="drop-shadow" />
      )}
    </svg>
  );
}

/** Radial gauge made of capsule segments, like the "Indicators" widget. */
export function SegmentedGauge({ value, segments = 15, size = 220 }: { value: number | null; segments?: number; size?: number }) {
  const v = Math.max(0, Math.min(100, value ?? 0)) / 100;
  const filled = Math.round(v * segments);
  const cx = size / 2;
  const cy = size * 0.56;
  const rIn = size * 0.3;
  const rOut = size * 0.44;
  const from = 195;
  const to = -15;
  const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t);
  const c0 = [15, 118, 110];
  const c1 = [94, 234, 212];
  return (
    <svg width={size} height={size * 0.78} viewBox={`0 0 ${size} ${size * 0.78}`}>
      {Array.from({ length: segments }).map((_, i) => {
        const t = segments === 1 ? 0 : i / (segments - 1);
        const deg = from + (to - from) * t;
        const [x1, y1] = toXY(cx, cy, rIn, deg);
        const [x2, y2] = toXY(cx, cy, rOut, deg);
        const on = i < filled;
        const k = filled > 1 ? i / (filled - 1) : 0;
        const color = `rgb(${lerp(c0[0], c1[0], k)},${lerp(c0[1], c1[1], k)},${lerp(c0[2], c1[2], k)})`;
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            strokeWidth={size * 0.062}
            strokeLinecap="round"
            stroke={on ? color : "currentColor"}
            className={on ? "" : "text-slate-200 dark:text-slate-700"}
          />
        );
      })}
    </svg>
  );
}

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  detail?: string;
}

/** Rounded "pill" bar chart with a highlighted bar and a floating tooltip. */
export function PillBars({ data, height = 190, highlight }: { data: BarDatum[]; height?: number; highlight?: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const max = useMemo(() => {
    const m = Math.max(1, ...data.map((d) => d.value));
    const step = m <= 4 ? 1 : m <= 10 ? 2 : m <= 20 ? 5 : Math.ceil(m / 4 / 5) * 5;
    return Math.ceil(m / step) * step;
  }, [data]);
  const active = hover ?? highlight ?? null;
  const ticks = [1, 0.75, 0.5, 0.25, 0].map((t) => Math.round(max * t));
  const dense = data.length > 16;
  return (
    <div className="flex gap-3">
      <div className="flex flex-col justify-between pb-6 text-right text-[11px] text-slate-400" style={{ height }}>
        {ticks.map((t, i) => (
          <span key={i}>{t}</span>
        ))}
      </div>
      <div className="relative flex-1">
        <div className="absolute inset-x-0 top-0 flex flex-col justify-between" style={{ height: height - 24 }}>
          {ticks.map((_, i) => (
            <div key={i} className="border-t border-dashed border-slate-200/70 dark:border-slate-700/60" />
          ))}
        </div>
        <div className={clsx("relative flex items-end", dense ? "gap-1" : "gap-2 sm:gap-3")} style={{ height: height - 24 }}>
          {data.map((d, i) => {
            const isActive = active === d.key;
            const h = Math.max(d.value / max, d.value > 0 ? 0.06 : 0.035);
            const edge = i > data.length * 0.7 ? "right-0" : i < data.length * 0.3 ? "left-0" : "left-1/2 -translate-x-1/2";
            return (
              <div
                key={d.key}
                className="group relative flex h-full flex-1 cursor-pointer items-end justify-center"
                onMouseEnter={() => setHover(d.key)}
                onMouseLeave={() => setHover(null)}
              >
                {hover === d.key && (
                  <div
                    className={clsx(
                      "pointer-events-none absolute z-10 mb-2 whitespace-nowrap rounded-xl bg-panel px-3 py-2 text-xs shadow-float ring-1 ring-line dark:bg-panel-dark dark:ring-line-dark",
                      edge,
                    )}
                    style={{ bottom: `${Math.min(h, 0.72) * 100}%` }}
                  >
                    <div className="text-[10px] text-slate-400">{d.label}</div>
                    <div className="flex items-center gap-1.5 font-semibold">
                      <span className="h-2 w-2 rounded-sm bg-brand-500" />
                      {d.value} violation{d.value === 1 ? "" : "s"}
                    </div>
                    {d.detail && <div className="text-[10px] text-slate-500">{d.detail}</div>}
                  </div>
                )}
                <div
                  className={clsx(
                    "relative w-full rounded-full transition-all duration-300",
                    dense ? "max-w-[18px]" : "max-w-[46px]",
                    isActive
                      ? "bg-gradient-to-t from-brand-200 via-brand-400 to-brand-600 shadow-glow"
                      : "bg-gradient-to-t from-brand-50/0 via-brand-100 to-brand-200/90 dark:from-brand-900/0 dark:via-brand-900/60 dark:to-brand-700/60",
                  )}
                  style={{ height: `${h * 100}%` }}
                >
                  {isActive && (
                    <span className="absolute left-1/2 top-1.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 border-brand-600 bg-white" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className={clsx("mt-2 flex", dense ? "gap-1" : "gap-2 sm:gap-3")}>
          {data.map((d, i) => (
            <div
              key={d.key}
              className={clsx(
                "flex-1 text-center text-[11px]",
                active === d.key ? "font-semibold text-brand-700 dark:text-brand-300" : "text-slate-400",
              )}
            >
              {!dense || i % 5 === 0 || i === data.length - 1 ? d.label : ""}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
