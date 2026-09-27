import { categoryAgreement, extractAgreement } from "@/lib/compare"
import { count, seconds, usd } from "@/lib/format"
import type { PanelState } from "@/hooks/useDuel"
import type { Completed, ReceiptExtraction, Task, TransactionCategories } from "@/lib/types"
import { modelTitle } from "@/lib/models"
import { cn } from "@/lib/utils"

type Metric = { label: string; value: (c: Completed) => number | null; show: (c: Completed) => string }

const METRICS: Metric[] = [
  { label: "Time", value: (c) => c.latency_ms, show: (c) => seconds(c.latency_ms) },
  { label: "First token", value: (c) => c.ttft_ms, show: (c) => seconds(c.ttft_ms) },
  { label: "Tokens", value: (c) => c.input_tokens + c.output_tokens, show: (c) => count(c.input_tokens + c.output_tokens) },
  { label: "Cost", value: (c) => c.cost_usd, show: (c) => usd(c.cost_usd) },
  {
    label: "Per 1,000 docs",
    value: (c) => (c.cost_usd == null ? null : c.cost_usd * 1000),
    show: (c) => usd(c.cost_usd == null ? null : c.cost_usd * 1000),
  },
]

const anim = (d: number) => ({ ["--d" as string]: `${d}ms` })

export function StatsTable({ panels }: { panels: PanelState[] }) {
  const done = panels.filter((p) => p.completed)
  if (done.length === 0)
    return (
      <section aria-label="Analytics" className="surface rise rounded-xl px-5 py-5 sm:px-6" style={anim(320)}>
        <h2 className="font-serif text-[19px] font-semibold">Analytics</h2>
        <p className="mt-1 text-ink-3">
          Time, first token, tokens and cost for each model, plus cost per 1,000 documents, appear here after a run.
        </p>
      </section>
    )
  const best = METRICS.map((m) => {
    const vals = done.map((p) => m.value(p.completed!)).filter((v): v is number => v != null)
    return vals.length > 1 ? Math.min(...vals) : null
  })
  return (
    <section aria-label="Analytics" className="surface rise overflow-x-auto rounded-xl p-2" style={anim(320)}>
      <h2 className="px-3.5 pt-3 font-serif text-[19px] font-semibold">Analytics</h2>
      <table className="w-full min-w-[560px] text-left">
        <caption className="sr-only">Speed and cost for each model</caption>
        <thead>
          <tr className="text-xs text-ink-3">
            <th className="px-3.5 py-2.5 font-normal">
              <span className="sr-only">Model</span>
            </th>
            {METRICS.map((m) => (
              <th key={m.label} scope="col" className="px-3.5 py-2.5 font-normal">
                {m.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {done.map((p) => (
            <tr key={p.key} className="[&>*]:border-t [&>*]:border-line">
              <th scope="row" className="px-3.5 py-2.5 font-medium">
                {modelTitle(p.key)}
              </th>
              {METRICS.map((m, i) => {
                const v = m.value(p.completed!)
                return (
                  <td key={m.label} className={cn("num px-3.5 py-2.5", v != null && v === best[i] && "text-sage")}>
                    {m.show(p.completed!)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function Verdict({ task, panels }: { task: Task | null; panels: PanelState[] }) {
  const finished = panels.length >= 2 && panels.every((p) => p.status === "done" || p.status === "error")
  const [a, b] = panels.map((p) => (p.completed?.schema_valid ? p.completed.output : null))

  let big: string | null = null
  let text = "Run a duel to see how the two answers compare."
  if (finished && task) {
    if ((task === "extract" || task === "categorise") && a && b) {
      const r =
        task === "extract"
          ? extractAgreement(a as ReceiptExtraction, b as ReceiptExtraction)
          : categoryAgreement(a as TransactionCategories, b as TransactionCategories)
      big = `${r.agree}/${r.total}`
      text = `The models agree on ${r.agree} of ${r.total} ${task === "extract" ? "fields" : "rows"}. Green values match, amber rows are where they differ. Agreement is not accuracy: for your own documents we don't know the right answer.`
    } else if (task === "extract" || task === "categorise") {
      text = "Only one model gave a usable answer, so there is nothing to compare."
    } else {
      text = "This task is unscored. Read both answers and judge for yourself."
    }
  } else if (task && panels.length) {
    text = "Both models are working. The summary appears when they finish."
  }
  const showLegend = task === "extract" || task === "categorise"

  return (
    <section aria-label="Summary" className="surface rise rounded-xl px-5 py-5 sm:px-6" style={anim(400)}>
      <h2 className="font-serif text-[19px] font-semibold">Summary</h2>
      <div className="mt-2 flex items-center gap-5">
        {big && <div className="num text-[28px] leading-none whitespace-nowrap">{big}</div>}
        <p className="text-ink-2" aria-live="polite">{text}</p>
      </div>
      {showLegend && finished && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="size-3 rounded-[3px] border border-sage bg-sage-bg" />
            Both models agree
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-3 rounded-[3px] border border-amber bg-amber-bg" />
            Models disagree
          </span>
        </div>
      )}
    </section>
  )
}
