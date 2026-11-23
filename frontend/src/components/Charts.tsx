import { RefObject, useEffect, useRef, useState } from "react";
import { Tip, Tooltip } from "./ui";

/** Width of a container in CSS px, so charts are drawn 1:1 and their text never scales down. */
export function useWidth<T extends HTMLElement>(fallback = 640): [RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export const SERIES = [
  { key: "baseline", label: "Baseline", color: "var(--series-baseline)" },
  { key: "improved", label: "Improved", color: "var(--series-improved)" },
] as const;
export type SeriesKey = (typeof SERIES)[number]["key"];

export function Legend() {
  return (
    <div className="legend">
      {SERIES.map((s) => <span key={s.key}><i style={{ background: s.color }} />{s.label}</span>)}
    </div>
  );
}

/** Bar with a 4px rounded data end and a square base on the baseline. */
function vbar(x: number, y: number, w: number, h: number, r = 4): string {
  if (h <= 0) return "";
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`;
}
function hbar(x: number, y: number, w: number, h: number, r = 4): string {
  if (w <= 0) return "";
  const rr = Math.min(r, w, h / 2);
  return `M${x},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h - rr} Q${x + w},${y + h} ${x + w - rr},${y + h} H${x} Z`;
}

export interface Group { label: string; sub?: string; values: Record<SeriesKey, number | null> }

/** Grouped vertical bars on a 0..1 scale. Direct value labels only on the groups listed in `labelGroups`. */
export function GroupedBars({ groups, height = 300, labelGroups = [] }: { groups: Group[]; height?: number; labelGroups?: number[] }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [box, W] = useWidth<HTMLDivElement>();
  const padL = 40, padR = 8, padT = 22, padB = 46;
  const plotW = W - padL - padR, plotH = height - padT - padB;
  const gw = plotW / groups.length, bw = Math.min(34, gw / 3.2), gap = 2;
  const yOf = (v: number) => padT + plotH * (1 - v);
  return (
    <div ref={box}>
      <svg className="chart" width={W} height={height} viewBox={`0 0 ${W} ${height}`} onMouseLeave={() => setTip(null)}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={yOf(t)} y2={yOf(t)} stroke="rgba(148,163,196,0.1)" strokeDasharray={t === 0 ? undefined : "2 4"} />
            <text x={padL - 8} y={yOf(t) + 4} textAnchor="end">{t * 100}%</text>
          </g>
        ))}
        {groups.map((g, i) => {
          const center = padL + gw * i + gw / 2;
          return (
            <g key={g.label}>
              {SERIES.map((s, j) => {
                const v = g.values[s.key];
                const bx = center - bw - gap / 2 + j * (bw + gap);
                if (v == null) return null;
                return (
                  <g key={s.key}>
                    <path d={vbar(bx, yOf(v), bw, plotH * v)} fill={s.color} />
                    {labelGroups.includes(i) && (g.values.baseline !== g.values.improved
                      ? <text className="value" x={bx + bw / 2} y={yOf(v) - 7} textAnchor="middle">{Math.round(v * 100)}%</text>
                      : j === 0 && <text className="value" x={center} y={yOf(v) - 7} textAnchor="middle">{Math.round(v * 100)}% both</text>)}
                  </g>
                );
              })}
              <rect x={center - gw / 2} y={padT} width={gw} height={plotH} fill="transparent"
                onMouseMove={(e) => setTip({
                  x: e.clientX, y: e.clientY, title: `${g.label}${g.sub ? ` · ${g.sub}` : ""}`,
                  rows: SERIES.map((s) => [s.label, g.values[s.key] == null ? "n/a" : `${Math.round((g.values[s.key] as number) * 100)}%`]),
                })} />
              <text className="axis-label" x={center} y={height - padB + 20} textAnchor="middle" style={{ fontWeight: 600 }}>{g.label}</text>
              {g.sub && <text x={center} y={height - padB + 36} textAnchor="middle">{g.sub}</text>}
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

export interface MetricRow { label: string; values: Record<SeriesKey, number | null>; format?: (v: number) => string; max?: number; lowerIsBetter?: boolean }

/** One row per metric, two thin horizontal bars (Baseline / Improved) with values at the bar ends. */
export function MetricBars({ rows }: { rows: MetricRow[] }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [box, W] = useWidth<HTMLDivElement>();
  // Wide: label | bars | value.  Narrow: the label sits above the bars so it never collides with them.
  const stacked = W < 560;
  const labelW = stacked ? 0 : 200, valueW = 62, barH = 9, labelH = stacked ? 18 : 0, rowH = stacked ? 54 : 42;
  const plotW = W - labelW - valueW;
  const height = rows.length * rowH + 6;
  return (
    <div ref={box}>
      <svg className="chart" width={W} height={height} viewBox={`0 0 ${W} ${height}`} onMouseLeave={() => setTip(null)}>
        {rows.map((r, i) => {
          const top = i * rowH + 8;
          const fmt = r.format ?? ((v: number) => `${Math.round(v * 100)}%`);
          const max = r.max ?? 1;
          return (
            <g key={r.label}>
              <text className="axis-label" x={0} y={top + (stacked ? 4 : 15)} style={{ fontSize: 12 }}>
                {r.label}{stacked && r.lowerIsBetter && <tspan style={{ fontSize: 10, fill: "var(--text-3)" }}>  · lower is better</tspan>}
              </text>
              {!stacked && r.lowerIsBetter && <text x={0} y={top + 30} style={{ fontSize: 10 }}>lower is better</text>}
              <rect x={labelW} y={top + 1 + labelH} width={plotW} height={barH * 2 + 2} fill="rgba(148,163,196,0.05)" rx={4} />
              {SERIES.map((s, j) => {
                const v = r.values[s.key];
                const by = top + 1 + labelH + j * (barH + 2);
                return (
                  <g key={s.key}>
                    {v != null && <path d={hbar(labelW, by, Math.max(2, (plotW * v) / max), barH)} fill={s.color} />}
                    <text x={W - valueW + 8} y={by + barH - 1} style={{ fontSize: 11, fill: "var(--text-2)", fontVariantNumeric: "tabular-nums" }}>
                      {v == null ? "n/a" : fmt(v)}
                    </text>
                  </g>
                );
              })}
              <rect x={0} y={top - 4} width={W} height={rowH - 4} fill="transparent"
                onMouseMove={(e) => setTip({
                  x: e.clientX, y: e.clientY, title: r.label,
                  rows: SERIES.map((s) => [s.label, r.values[s.key] == null ? "n/a" : fmt(r.values[s.key] as number)]),
                })} />
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

/** Single-value ring (spend vs. budget). */
export function Ring({ value, max, size = 92, label }: { value: number; max: number; size?: number; label: string }) {
  const r = size / 2 - 8, c = 2 * Math.PI * r;
  const frac = Math.min(1, max ? value / max : 0);
  const color = frac > 0.85 ? "var(--bad)" : frac > 0.6 ? "var(--warn)" : "url(#ringGrad)";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
      <defs>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22d3ee" /><stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(148,163,196,0.12)" strokeWidth={8} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
        strokeDasharray={`${c * frac} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dy="0.35em" style={{ fill: "var(--text)", fontSize: 15, fontWeight: 700 }}>
        {Math.round(frac * 100)}%
      </text>
    </svg>
  );
}
