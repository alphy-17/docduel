import { useEffect, useState } from "react"

import { BulletsView, CategoriesView, ExtractView, Pager, TextView } from "@/components/outputs/Views"
import type { PanelState } from "@/hooks/useDuel"
import { count, seconds } from "@/lib/format"
import { modelTitle } from "@/lib/models"
import type {
  CategoriseTruth,
  ExtractTruth,
  ReceiptExtraction,
  SummaryOutput,
  Task,
  TransactionCategories,
} from "@/lib/types"
import { cn } from "@/lib/utils"

const ERRORS: Record<string, string> = {
  auth_failed: "The model's API key was rejected, so it could not answer.",
  timeout: "No complete answer within 60 seconds.",
  rate_limited: "The model's API is busy or out of credit. Try again shortly.",
  connection_error: "Could not reach the model's server.",
  not_configured: "This model is not set up yet.",
  api_error: "The model's API returned an error.",
}

interface Props {
  delay: number
  panel: PanelState
  other?: PanelState
  task: Task
  placeholder: boolean
  modelId?: string | null
  rowLabels?: string[]
  page?: number
  onPage?: (p: number) => void
  truth?: ExtractTruth | CategoriseTruth
}

export function ModelPanel({ delay, panel, other, task, placeholder, modelId, rowLabels, page = 0, onPage, truth }: Props) {
  const c = panel.completed
  const otherOut = other?.completed?.schema_valid ? other.completed.output : undefined

  return (
    <article
      aria-busy={panel.status === "waiting" || panel.status === "streaming"}
      className="surface rise flex min-h-[260px] min-w-0 flex-col rounded-xl px-5 pt-5 pb-4"
      style={{ ["--d" as string]: `${delay}ms` }}
    >
      <header className="mb-1 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <h2 className="font-serif text-[21px] font-semibold">{modelTitle(panel.key)}</h2>
        <span className="text-xs text-ink-3">{modelId ?? panel.key}</span>
        {placeholder && (
          <span
            className="ml-auto rounded-full border border-dashed border-clay/60 px-2.5 py-px text-[11px] text-clay"
            title="The real small model (Qwen) replaces this in Phase 6"
          >
            stand-in until Qwen
          </span>
        )}
      </header>

      <StatusLine panel={panel} />

      <div className="mt-3.5" aria-live="polite">
        {panel.status === "idle" && (
          <p className="text-ink-3">The answer appears here, written out live as the model replies.</p>
        )}
        {panel.status === "waiting" && <Waiting panel={panel} />}
        {panel.status === "streaming" && (
          <pre className="num caret max-h-72 overflow-auto text-xs leading-relaxed whitespace-pre-wrap text-ink-2">
            {panel.text}
          </pre>
        )}
        {panel.status === "error" && (
          <p className="rounded-md bg-rust-bg px-3 py-2.5 text-rust">
            {ERRORS[panel.error?.error_code ?? ""] ?? panel.error?.message ?? "Something went wrong."}
          </p>
        )}
        {panel.status === "done" && c && (
          c.schema_valid === false ? (
            <div>
              <p className="mb-2 rounded-md bg-rust-bg px-3 py-2.5 text-rust">
                The answer did not match the required format, so it scores zero.
              </p>
              <pre className="num max-h-56 overflow-auto text-xs whitespace-pre-wrap text-ink-2">{panel.text || String(c.output)}</pre>
            </div>
          ) : task === "extract" ? (
            <ExtractView
              out={c.output as ReceiptExtraction}
              other={otherOut as ReceiptExtraction | undefined}
              truth={truth as ExtractTruth | undefined}
            />
          ) : task === "categorise" ? (
            <>
              <CategoriesView
                out={c.output as TransactionCategories}
                other={otherOut as TransactionCategories | undefined}
                labels={rowLabels}
                page={page}
                truth={truth as CategoriseTruth | undefined}
              />
              {onPage && <Pager page={page} total={(c.output as TransactionCategories).items.length} onPage={onPage} />}
            </>
          ) : task === "summarise" ? (
            <BulletsView out={c.output as SummaryOutput} />
          ) : (
            <TextView text={String(c.output)} />
          )
        )}
      </div>
    </article>
  )
}

function StatusLine({ panel }: { panel: PanelState }) {
  const c = panel.completed
  const label = { idle: "Ready", waiting: "Waiting", streaming: "Writing", done: "Done", error: "Failed" }[panel.status]
  return (
    <div className="flex flex-wrap gap-x-4 text-xs text-ink-2">
      <span className="inline-flex items-center gap-1.5">
        <span
          className={cn(
            "size-[7px] rounded-full",
            panel.status === "idle" && "bg-line-2",
            panel.status === "done" && "bg-sage",
            panel.status === "error" && "bg-rust",
            (panel.status === "waiting" || panel.status === "streaming") && "animate-pulse bg-clay",
          )}
        />
        {label}
      </span>
      {c?.latency_ms != null && <span className="num">{seconds(c.latency_ms)}</span>}
      {c && <span className="num">{count(c.output_tokens)} tokens out</span>}
      {c?.cold_start && <span>GPU was asleep</span>}
    </div>
  )
}

function Waiting({ panel }: { panel: PanelState }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const waited = (now - panel.startedAt) / 1000
  const gpu = panel.key.startsWith("small-")
  return (
    <div>
      <div className="space-y-2.5" aria-hidden="true">
        {[92, 70, 84, 56].map((w) => (
          <div key={w} className="h-3 animate-pulse rounded-full bg-wash" style={{ width: `${w}%` }} />
        ))}
      </div>
      {waited > 10 && (
        <p className="mt-4 text-[13px] text-ink-2">
          {gpu ? "Waking up the GPU. The first run after a quiet spell can take a minute." : "Still thinking. Longer documents take a little more time."}
        </p>
      )}
    </div>
  )
}
