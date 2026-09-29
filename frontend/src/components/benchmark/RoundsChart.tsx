import { useState } from "react"

import type { Benchmark, RoundMetrics } from "@/lib/types"

// Plan 8.9: base -> round 1 -> round 2, only from reports/*.json via GET /api/benchmark (rule R5).

const LABELS: Record<string, string> = { "small-base": "Base", "small-ft-r1": "Round 1", "small-ft-r2": "Round 2" }
const pct = (v: number) => `${(v * 100).toFixed(1)}%`
const LO = 0.5 // both panels share one 50-100% scale so they can be compared honestly
const W = 540
const H = 250
const PAD = { l: 44, r: 20, t: 16, b: 34 }
const y = (v: number) => PAD.t + (1 - (Math.max(v, LO) - LO) / (1 - LO)) * (H - PAD.t - PAD.b)
const x = (i: number) => PAD.l + 50 + i * ((W - PAD.l - PAD.r - 100) / 2)

type Point = { key: string; m: RoundMetrics }

function Panel({ title, points, reference }: { title: string; points: Point[]; reference?: RoundMetrics | null }) {
  const [hover, setHover] = useState<number | null>(null)
  const fa = (p: Point) => p.m.field_accuracy!
  const shown = points.filter((p) => p.m.field_accuracy)
  const path = shown.map((p, i) => `${i ? "L" : "M"}${x(points.indexOf(p))},${y(fa(p).value)}`).join(" ")
  const ref = reference?.field_accuracy

  return (
    <figure className="relative min-w-0">
      <figcaption className="mb-1 text-[14px] font-medium">
        {title}
        {shown[0] && <span className="font-normal text-ink-3"> · {shown[0].m.docs} documents</span>}
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${title}: field accuracy by round`}>
        {[0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} className="stroke-line" strokeWidth={1} />
            <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" className="num fill-ink-3 text-[11px]">
              {t * 100}%
            </text>
          </g>
        ))}
        {ref && (
          <g>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y(ref.value)}
              y2={y(ref.value)}
              className="stroke-series-openai"
              strokeWidth={1.5}
              strokeDasharray="5 4"
            />
            <text x={PAD.l + 6} y={y(ref.value) - 6} className="fill-ink-2 text-[11px]">
              OpenAI {pct(ref.value)}
            </text>
          </g>
        )}
        <path d={path} fill="none" className="stroke-series-ours" strokeWidth={2} />
        {points.map((p, i) => {
          const m = p.m.field_accuracy
          const cx = x(i)
          return (
            <g key={p.key}>
              <text x={cx} y={H - 10} textAnchor="middle" className="fill-ink-2 text-[12px]">
                {LABELS[p.key] ?? p.key}
              </text>
              {m ? (
                <g
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(i)}
                  onBlur={() => setHover(null)}
                  tabIndex={0}
                  aria-label={`${LABELS[p.key]}: ${m.display}`}
                  className="cursor-default outline-none"
                >
                  <line
                    x1={cx}
                    x2={cx}
                    y1={y(m.ci95[0])}
                    y2={y(m.ci95[1])}
                    className="stroke-series-ours"
                    strokeOpacity={0.45}
                    strokeWidth={2}
                    strokeLinecap="round"
                  />
                  <circle
                    cx={cx}
                    cy={y(m.value)}
                    r={5}
                    className="fill-series-ours stroke-card-solid"
                    strokeWidth={2}
                  />
                  <circle cx={cx} cy={y(m.value)} r={16} fill="transparent" />
                  <text
                    x={i === points.length - 1 ? cx - 12 : cx + 12}
                    y={y(m.value) + 4}
                    textAnchor={i === points.length - 1 ? "end" : "start"}
                    className="num fill-foreground text-[12px] font-medium"
                  >
                    {pct(m.value)}
                  </text>
                </g>
              ) : (
                <text x={cx} y={y(0.75)} textAnchor="middle" className="fill-ink-3 text-[11px]">
                  not run
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {hover !== null && points[hover]?.m.field_accuracy && (
        <div
          role="status"
          className="pointer-events-none absolute top-8 z-10 rounded-lg whitespace-nowrap border border-line-2 bg-card-solid px-3 py-2 text-[12px] shadow-md"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: "translateX(-50%)" }}
        >
          <p className="font-medium">{LABELS[points[hover].key]}</p>
          <p className="num text-ink-2">Fields {points[hover].m.field_accuracy!.display}</p>
          {points[hover].m.line_item_f1 && (
            <p className="num text-ink-2">Line items {points[hover].m.line_item_f1!.display}</p>
          )}
          {points[hover].m.perfect_document_rate && (
            <p className="num text-ink-2">Perfect docs {points[hover].m.perfect_document_rate!.display}</p>
          )}
        </div>
      )}
    </figure>
  )
}

export function RoundsChart({ data }: { data: Benchmark }) {
  const rounds = data.rounds
  if (!rounds || !rounds.models.some((r) => r.test || r.holdout)) return null
  const test = rounds.models.filter((r) => r.test).map((r) => ({ key: r.key, m: r.test! }))
  const hold = rounds.models.filter((r) => r.holdout).map((r) => ({ key: r.key, m: r.holdout! }))
  const rows: [string, (m: RoundMetrics) => string][] = [
    ["Field accuracy", (m) => m.field_accuracy?.display ?? "-"],
    ["Line-item F1", (m) => m.line_item_f1?.display ?? "-"],
    ["Perfect documents", (m) => m.perfect_document_rate?.display ?? "-"],
  ]

  return (
    <section
      aria-label="Improvement over rounds"
      className="surface rise rounded-xl px-5 py-5 sm:px-6"
      style={{ ["--d" as string]: "420ms" }}
    >
      <h2 className="font-serif text-[19px] font-semibold">Improvement over rounds</h2>
      <p className="mt-1 max-w-[760px] text-ink-2">
        Field accuracy of our small model before fine-tuning, after round 1 (training data) and after round 2 (plus 40
        human-corrected hard invoices). Dots are scores, the faint bars their 95% ranges. None of these documents were
        used for training.
      </p>
      <div className="mt-4 grid gap-6 md:grid-cols-2">
        <Panel title="Frozen test set" points={test} reference={rounds.baseline_test} />
        <Panel title="Hard held-out invoices" points={hold} />
      </div>
      <details className="mt-4">
        <summary className="cursor-pointer text-[14px] font-medium text-ink-2">Show as a table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-[13px]">
            <thead className="text-ink-3">
              <tr>
                <th className="py-1.5 pr-3 font-medium">Set</th>
                <th className="py-1.5 pr-3 font-medium">Metric</th>
                {rounds.models.map((r) => (
                  <th key={r.key} className="py-1.5 pr-3 font-medium">
                    {LABELS[r.key]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(["test", "holdout"] as const).flatMap((set) =>
                rows.map(([name, get]) => (
                  <tr key={set + name} className="border-t border-line">
                    <td className="py-1.5 pr-3 text-ink-2">{set === "test" ? "Test set" : "Hard held-out"}</td>
                    <td className="py-1.5 pr-3">{name}</td>
                    {rounds.models.map((r) => (
                      <td key={r.key} className="num py-1.5 pr-3">
                        {r[set] ? get(r[set]!) : "not run"}
                      </td>
                    ))}
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
