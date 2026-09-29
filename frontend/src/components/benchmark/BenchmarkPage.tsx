import { ChevronRight } from "lucide-react"
import { useEffect, useState } from "react"

import { getBenchmark } from "@/lib/api"
import { EXTRACT_FIELDS } from "@/lib/compare"
import { seconds, usd } from "@/lib/format"
import type { Benchmark, BenchmarkModel, Failure, LineItem, Metric } from "@/lib/types"
import { cn } from "@/lib/utils"

import { RoundsChart } from "./RoundsChart"

// Every number on this page comes from reports/*.json through GET /api/benchmark (rule R5).

const anim = (d: number) => ({ ["--d" as string]: `${d}ms` })
const pct = (v: number) => `${(v * 100).toFixed(1)}%`

const SOURCES: Record<string, string> = {
  cord: "CORD receipt",
  synthetic_invoice: "Invoice",
  owner: "Real receipt",
}

const FIELD_LABELS: Record<string, string> = Object.fromEntries(EXTRACT_FIELDS.map((f) => [f.key, f.label]))

export function BenchmarkPage() {
  const [data, setData] = useState<Benchmark | null>(null)
  const [failed, setFailed] = useState(false)
  const [focus, setFocus] = useState<"ours" | "baseline">("baseline")

  useEffect(() => {
    getBenchmark()
      .then(setData)
      .catch(() => setFailed(true))
  }, [])

  if (failed)
    return (
      <Card title="Benchmark" delay={0}>
        <p className="text-ink-2">Can't reach the backend. Start it with uvicorn on port 8000, then reload.</p>
      </Card>
    )
  if (!data)
    return (
      <Card title="Benchmark" delay={0}>
        <div className="space-y-2.5" aria-hidden="true">
          {[80, 64, 72].map((w) => (
            <div key={w} className="h-3 animate-pulse rounded-full bg-wash" style={{ width: `${w}%` }} />
          ))}
        </div>
      </Card>
    )

  const base = data.models[data.baseline]
  const ours = data.ours ? data.models[data.ours] : null
  if (!base.extract)
    return (
      <Card title="Benchmark" delay={0}>
        <p className="text-ink-2">
          No test-set report yet. Run <code className="num">python -m docduel.eval</code> on {data.dataset_version} to
          create one.
        </p>
      </Card>
    )

  const shown = focus === "ours" && ours ? ours : base
  const extractDocs = base.extract.docs
  const cat = base.categorise

  return (
    <>
      <section className="surface rise rounded-xl px-5 py-5 sm:px-7 sm:py-6" style={anim(0)}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-[720px]">
            <h1 className="font-serif text-[30px] leading-tight font-bold sm:text-[34px]">Benchmark</h1>
            <p className="mt-2 text-[15px] text-ink-2">
              Both models answer the same frozen test set ({data.dataset_version}): {extractDocs} receipts and invoices
              {cat ? `, plus ${cat.docs} bank CSVs with ${cat.rows} rows` : ""}. Every answer is checked against the
              true answer. The small grey ranges are 95% confidence intervals: with this many documents, the true score
              is very likely inside them.
            </p>
          </div>
          {ours && (
            <div role="group" aria-label="Show details for" className="flex rounded-full bg-wash p-1">
              {(["ours", "baseline"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={focus === k}
                  onClick={() => setFocus(k)}
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors",
                    focus === k ? "bg-card-solid shadow-sm" : "text-ink-2 hover:text-foreground",
                  )}
                >
                  {k === "ours" ? "Our model" : "OpenAI"}
                </button>
              ))}
            </div>
          )}
        </div>
        <p className="mt-3 text-xs text-ink-3">
          Last run {new Date(base.extract.created_at).toLocaleDateString("en-AU", { dateStyle: "medium" })} · prompt{" "}
          {data.prompt_version}
        </p>
      </section>

      <Headline data={data} base={base} ours={ours} />

      <div className="grid gap-5 lg:grid-cols-2">
        <FieldBars base={base} ours={ours} />
        <ConfusionMatrix model={shown} who={shown === ours ? "Our model" : "OpenAI"} />
      </div>

      <Failures model={shown} who={shown === ours ? "our model" : "OpenAI"} />

      <RoundsChart data={data} />

      <Card title="How we score" delay={480}>
        <ul className="list-disc space-y-1 pl-5 text-ink-2">
          {base.extract.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          <li>Categorise: a missing or extra row counts as wrong.</li>
          <li>Speed excludes OCR time, which is the same for both models.</li>
        </ul>
      </Card>
    </>
  )
}

function Card({
  title,
  delay,
  children,
  className,
}: {
  title: string
  delay: number
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      aria-label={title}
      className={cn("surface rise rounded-xl px-5 py-5 sm:px-6", className)}
      style={anim(delay)}
    >
      <h2 className="font-serif text-[19px] font-semibold">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

/* ---------------------------------------------------------------- headline */

type Row = { label: string; hint?: string; cell: (m: BenchmarkModel) => React.ReactNode }

function metricCell(m: Metric | number | undefined) {
  if (m === undefined) return <span className="text-ink-3">n/a</span>
  if (typeof m === "number") return <span className="num">{pct(m)}</span>
  // Show the report's own formatted text so the page matches reports/*.json exactly (rule R5).
  const [value, range] = m.display.split(" ")
  return (
    <span className="num">
      <span className="text-[15px] font-medium">{value}</span> <span className="text-xs text-ink-3">{range}</span>
    </span>
  )
}

const ROWS: Row[] = [
  {
    label: "Field accuracy",
    hint: "Share of known fields (total, tax, date...) read correctly",
    cell: (m) => metricCell(m.extract?.headline.field_accuracy),
  },
  {
    label: "Line-item F1",
    hint: "How well purchased items and their prices were listed",
    cell: (m) => metricCell(m.extract?.headline.line_item_f1),
  },
  {
    label: "Perfect documents",
    hint: "Every field and every item right",
    cell: (m) => metricCell(m.extract?.headline.perfect_document_rate),
  },
  {
    label: "Valid answers",
    hint: "Replies that matched the required format",
    cell: (m) => metricCell(m.extract?.headline.schema_validity),
  },
  {
    label: "Categorise accuracy",
    hint: "Bank rows given the right category",
    cell: (m) => metricCell(m.categorise?.headline.accuracy),
  },
  {
    label: "Speed, typical / slow",
    hint: "Median and 95th percentile time per receipt",
    cell: (m) =>
      m.extract ? (
        <span className="num">
          {seconds(m.extract.speed_cost.latency_ms_p50)} / {seconds(m.extract.speed_cost.latency_ms_p95)}
        </span>
      ) : null,
  },
  {
    label: "Cost per 1,000 docs",
    hint: "OpenAI: tokens x list price. Our GPU: one at a time, and at steady load",
    cell: (m) => {
      if (!m.extract) return null
      const sc = m.extract.speed_cost
      return (
        <span className="num">
          {usd(sc.cost_per_1000_docs_usd)}
          {sc.steady_load && (
            <span className="block text-xs text-ink-3">
              {usd(sc.steady_load.cost_per_1000_docs_usd)} at steady load ({sc.steady_load.concurrency} in flight)
            </span>
          )}
        </span>
      )
    },
  },
]

function Headline({ data, base, ours }: { data: Benchmark; base: BenchmarkModel; ours: BenchmarkModel | null }) {
  return (
    <section aria-label="Headline results" className="surface rise overflow-x-auto rounded-xl p-2" style={anim(160)}>
      <h2 className="px-3.5 pt-3 font-serif text-[19px] font-semibold">Headline results</h2>
      <table className="w-full min-w-[560px] text-left">
        <caption className="sr-only">Headline test-set results for each model with 95% confidence intervals</caption>
        <thead>
          <tr className="text-xs text-ink-3">
            <th className="px-3.5 py-2.5 font-normal">
              <span className="sr-only">Metric</span>
            </th>
            <th scope="col" className="w-[30%] px-3.5 py-2.5 font-normal">
              <span className="inline-flex items-center gap-1.5">
                <span className="size-2.5 rounded-[3px] bg-series-ours" aria-hidden="true" />
                Our model
                {data.ours && (
                  <span className="text-ink-3">
                    ({data.ours}, {data.ours === "small-base" ? "not fine-tuned yet" : "fine-tuned, best on dev"})
                  </span>
                )}
              </span>
            </th>
            <th scope="col" className="w-[30%] px-3.5 py-2.5 font-normal">
              <span className="inline-flex items-center gap-1.5">
                <span className="size-2.5 rounded-[3px] bg-series-openai" aria-hidden="true" />
                OpenAI{" "}
                <span className="text-ink-3">
                  ({base.model_id}, {base.reasoning_effort} reasoning)
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r, i) => (
            <tr key={r.label} className="[&>*]:border-t [&>*]:border-line">
              <th scope="row" className="px-3.5 py-2.5 font-medium">
                {r.label}
                {r.hint && <span className="block text-xs font-normal text-ink-3">{r.hint}</span>}
              </th>
              <td className="px-3.5 py-2.5">
                {ours ? (
                  r.cell(ours)
                ) : i === 0 ? (
                  <span className="text-ink-3">Not trained yet (Phase 7)</span>
                ) : (
                  <span className="text-ink-3">-</span>
                )}
              </td>
              <td className="px-3.5 py-2.5">{r.cell(base)}</td>
            </tr>
          ))}
          {data.relative_score !== null && (
            <tr className="[&>*]:border-t [&>*]:border-line">
              <th scope="row" className="px-3.5 py-2.5 font-medium">
                Our score as a share of OpenAI's
                <span className="block text-xs font-normal text-ink-3">Field accuracy, ours divided by OpenAI's</span>
              </th>
              <td className="num px-3.5 py-2.5 text-[15px] font-medium" colSpan={2}>
                {data.relative_score.toFixed(1)}%
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  )
}

/* ---------------------------------------------------------------- field bars */

function FieldBars({ base, ours }: { base: BenchmarkModel; ours: BenchmarkModel | null }) {
  const fields = Object.entries(base.extract!.per_field)
  const series = [
    ...(ours?.extract ? [{ name: "Our model", cls: "bg-series-ours", pf: ours.extract.per_field }] : []),
    { name: "OpenAI", cls: "bg-series-openai", pf: base.extract!.per_field },
  ]
  return (
    <Card title="Accuracy by field" delay={260} className="min-w-0">
      <p className="mb-3 text-xs text-ink-3">
        Only fields the true answer knows are scored, so each field has its own number of documents (n).
      </p>
      <ul className="space-y-3">
        {fields.map(([key, v]) => (
          <li key={key}>
            <div className="mb-1 flex justify-between text-[13px]">
              <span>{FIELD_LABELS[key] ?? key}</span>
              <span className="text-xs text-ink-3">n = {v.scored}</span>
            </div>
            {series.map((s) => {
              const acc = s.pf[key]?.accuracy
              return (
                <div
                  key={s.name}
                  className="group flex items-center gap-2.5"
                  title={`${s.name}: ${acc === undefined ? "n/a" : pct(acc)}`}
                >
                  <div className="h-2.5 flex-1 rounded-full bg-wash">
                    <div
                      className={cn("h-full rounded-full transition-[width] duration-700", s.cls)}
                      style={{ width: `${(acc ?? 0) * 100}%` }}
                    />
                  </div>
                  <span className="num w-14 text-right text-xs">{acc === undefined ? "n/a" : pct(acc)}</span>
                  {series.length > 1 && <span className="sr-only">{s.name}</span>}
                </div>
              )
            })}
          </li>
        ))}
      </ul>
    </Card>
  )
}

/* ---------------------------------------------------------------- confusion matrix */

const SHORT: Record<string, string> = {
  Groceries: "Groc",
  Dining: "Dine",
  Transport: "Trans",
  Utilities: "Util",
  Shopping: "Shop",
  Health: "Health",
  Entertainment: "Ent",
  Other: "Other",
  "(missing)": "None",
}

function ConfusionMatrix({ model, who }: { model: BenchmarkModel; who: string }) {
  const cat = model.categorise
  if (!cat)
    return (
      <Card title="Categorise: where rows went" delay={320}>
        <p className="text-ink-3">No categorise report for {who} yet.</p>
      </Card>
    )
  const m = cat.confusion_matrix
  const truths = Object.keys(m).filter((t) => Object.values(m[t]).some((n) => n > 0))
  const cols = Object.keys(m[Object.keys(m)[0]]).filter(
    (c) => truths.includes(c) || Object.keys(m).some((t) => m[t][c] > 0),
  )
  const max = Math.max(1, ...truths.flatMap((t) => cols.map((c) => m[t][c])))
  return (
    <Card title="Categorise: where rows went" delay={320} className="min-w-0">
      <p className="mb-3 text-xs text-ink-3">
        {who}, {cat.rows} rows. Each row of the grid is the true category, each column the category the model chose. The
        diagonal is correct. Accuracy {pct(cat.headline.accuracy.value)}.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] table-fixed border-separate border-spacing-[3px] text-center text-xs">
          <caption className="sr-only">Confusion matrix: true category by predicted category, {who}</caption>
          <thead>
            <tr className="text-ink-3">
              <th className="w-[92px] text-left font-normal">
                <span className="sr-only">True category</span>
              </th>
              {cols.map((c) => (
                <th key={c} scope="col" className="font-normal" title={c}>
                  {SHORT[c] ?? c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {truths.map((t) => (
              <tr key={t}>
                <th scope="row" className="truncate pr-1 text-left font-normal text-ink-2">
                  {t}
                </th>
                {cols.map((c) => {
                  const n = m[t][c]
                  return (
                    <td
                      key={c}
                      title={`True ${t}, chose ${c}: ${n}`}
                      className={cn(
                        "num h-9 rounded-[6px]",
                        n === 0 && "text-ink-3/50",
                        t === c && "outline outline-1 outline-line-2",
                      )}
                      style={n > 0 ? { background: `rgb(var(--heat) / ${0.12 + (0.38 * n) / max})` } : undefined}
                    >
                      {n || ""}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

/* ---------------------------------------------------------------- failures */

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "nothing"
  return typeof v === "number" ? v.toLocaleString("en-AU") : String(v)
}

function Items({ title, items }: { title: string; items: LineItem[] | null }) {
  return (
    <div className="min-w-0">
      <p className="eyebrow mb-1.5">{title}</p>
      {!items || items.length === 0 ? (
        <p className="text-ink-3">none</p>
      ) : (
        <ul className="space-y-1">
          {items.map((it, i) => (
            <li key={i} className="flex gap-3">
              <span className="min-w-0 flex-1 truncate" title={it.description}>
                {it.description}
              </span>
              <span className="num shrink-0">{show(it.amount)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function FailureRow({ f }: { f: Failure }) {
  const wrong = Object.entries(f.wrong_fields)
  const itemsOff = f.items.tp < Math.max(f.items.gold, f.items.pred)
  return (
    <details className="group rounded-md border border-line bg-card-solid/60 open:bg-card-solid">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-1 px-3.5 py-2.5 [&::-webkit-details-marker]:hidden">
        <ChevronRight
          className="size-4 shrink-0 text-ink-3 transition-transform group-open:rotate-90"
          aria-hidden="true"
        />
        <span className="num font-medium">{f.id}</span>
        <span className="rounded-full bg-wash px-2 py-px text-[11px] text-ink-2">{SOURCES[f.source] ?? f.source}</span>
        <span className="num ml-auto text-xs text-ink-2">
          fields {f.fields} · items {f.items.tp}/{f.items.gold}
        </span>
      </summary>
      <div className="space-y-4 border-t border-line px-3.5 py-3 text-[13px]">
        {!f.valid && (
          <p className="text-rust">The answer did not match the required format, so every field scores zero.</p>
        )}
        {wrong.length > 0 && (
          <table className="w-full text-left">
            <thead>
              <tr className="text-xs text-ink-3">
                <th className="pb-1 font-normal">Field</th>
                <th className="pb-1 font-normal">True answer</th>
                <th className="pb-1 font-normal">Model said</th>
              </tr>
            </thead>
            <tbody>
              {wrong.map(([k, v]) => (
                <tr key={k} className="[&>td]:border-t [&>td]:border-line [&>td]:py-1.5">
                  <td>{FIELD_LABELS[k] ?? k}</td>
                  <td className="num">{show(v.expected)}</td>
                  <td className="num text-rust">{show(v.predicted)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {itemsOff && f.line_items && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Items title="True items" items={f.line_items.expected} />
            <Items title="Model's items" items={f.line_items.predicted} />
          </div>
        )}
      </div>
    </details>
  )
}

function Failures({ model, who }: { model: BenchmarkModel; who: string }) {
  const list = model.extract?.worst_failures ?? []
  return (
    <Card title="Worst failures" delay={400}>
      <p className="mb-3 text-ink-2">
        The documents {who} got most wrong. Open one to see the true answer next to what the model said. Many failures
        come from OCR text where prices drift away from their items, which is hard for any model.
      </p>
      {list.length === 0 ? (
        <p className="text-ink-3">No failures recorded.</p>
      ) : (
        <div className="space-y-2">
          {list.map((f) => (
            <FailureRow key={f.id} f={f} />
          ))}
        </div>
      )}
    </Card>
  )
}
