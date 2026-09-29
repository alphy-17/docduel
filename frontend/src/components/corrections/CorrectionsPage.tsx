import { ChevronLeft, ChevronRight, Minus, Plus, Trash2 } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { correctionImageUrl, getCorrection, getCorrections, saveCorrection } from "@/lib/api"
import { EXTRACT_FIELDS } from "@/lib/compare"
import type { CorrectionDoc, CorrectionList, LineItem, ReceiptExtraction } from "@/lib/types"
import { cn } from "@/lib/utils"

// Plan 8.2: the Owner checks our model's answer against the page and fixes it.
// The form is pre-filled from our fine-tuned model, never from OpenAI (rule R3).

const anim = (d: number) => ({ ["--d" as string]: `${d}ms` })
const ZOOMS = [1, 1.5, 2]

type Row = { description: string; quantity: string; unit_price: string; amount: string }
type Form = { fields: Record<string, string>; rows: Row[] }

const show = (v: unknown) => (v === null || v === undefined ? "" : String(v))

function toForm(a: ReceiptExtraction): Form {
  const fields: Record<string, string> = {}
  for (const f of EXTRACT_FIELDS) fields[f.key] = show(a[f.key])
  const rows = a.line_items.map((li) => ({
    description: li.description,
    quantity: show(li.quantity),
    unit_price: show(li.unit_price),
    amount: show(li.amount),
  }))
  return { fields, rows }
}

// "1,234.50" -> 1234.5; blank -> null; anything else -> NaN (blocks saving)
function num(s: string): number | null {
  const t = s.replace(/,/g, "").trim()
  if (!t) return null
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : NaN
}

function fromForm(f: Form): { answer: ReceiptExtraction; bad: string[] } {
  const bad: string[] = []
  const out: Record<string, unknown> = {}
  for (const d of EXTRACT_FIELDS) {
    const raw = f.fields[d.key] ?? ""
    if (d.kind === "money") {
      const n = num(raw)
      if (Number.isNaN(n)) bad.push(d.label)
      out[d.key] = n
    } else out[d.key] = raw.trim() || null
  }
  const items: LineItem[] = f.rows
    .filter((r) => r.description.trim() || r.amount.trim())
    .map((r, i) => {
      const [q, u, a] = [num(r.quantity), num(r.unit_price), num(r.amount)]
      if ([q, u, a].some(Number.isNaN)) bad.push(`line ${i + 1}`)
      return { description: r.description.trim(), quantity: q, unit_price: u, amount: a }
    })
  return { answer: { ...(out as Omit<ReceiptExtraction, "line_items">), line_items: items }, bad }
}

export function CorrectionsPage() {
  const [list, setList] = useState<CorrectionList | null>(null)
  const [failed, setFailed] = useState(false)
  const [current, setCurrent] = useState<string | null>(null)
  const [doc, setDoc] = useState<CorrectionDoc | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [zoom, setZoom] = useState(0)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    getCorrections()
      .then((l) => {
        setList(l)
        setCurrent((c) => c ?? l.items.find((i) => !i.verified)?.id ?? l.items[0]?.id ?? null)
      })
      .catch(() => setFailed(true))
  }, [])

  useEffect(() => {
    if (!current) return
    getCorrection(current)
      .then((d) => {
        setDoc(d)
        setForm(toForm(d.saved ?? d.prefill))
      })
      .catch(() => setMessage("Couldn't load this document."))
  }, [current])

  const prefill = useMemo(() => (doc ? toForm(doc.prefill) : null), [doc])
  const loaded = doc?.id === current
  const open = (id: string) => {
    setMessage(null)
    setCurrent(id)
  }
  const index = list && current ? list.items.findIndex((i) => i.id === current) : -1
  const go = (step: number) => {
    if (!list || index < 0) return
    const next = list.items[(index + step + list.items.length) % list.items.length]
    open(next.id)
  }

  const edited = useMemo(() => {
    if (!form || !prefill) return 0
    const f = EXTRACT_FIELDS.filter((d) => form.fields[d.key] !== prefill.fields[d.key]).length
    return f + (JSON.stringify(form.rows) !== JSON.stringify(prefill.rows) ? 1 : 0)
  }, [form, prefill])

  const save = useCallback(async () => {
    if (!form || !current || !list || saving) return
    const { answer, bad } = fromForm(form)
    if (bad.length) {
      setMessage(`Use plain numbers in: ${bad.join(", ")}.`)
      return
    }
    setSaving(true)
    try {
      const r = await saveCorrection(current, answer)
      const items = list.items.map((i) =>
        i.id === current ? { ...i, verified: true, changed_fields: r.changed_fields } : i,
      )
      setList({ ...list, items, verified: r.verified })
      const next = items.slice(index + 1).find((i) => !i.verified) ?? items.find((i) => !i.verified)
      if (next) open(next.id)
      else setMessage("All documents verified. Thank you.")
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Saving failed.")
    } finally {
      setSaving(false)
    }
  }, [form, current, list, saving, index])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault()
        void save()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [save])

  if (failed)
    return (
      <Panel title="Corrections" delay={0}>
        <p className="text-ink-2">Can't reach the backend. Start it with uvicorn on port 8000, then reload.</p>
      </Panel>
    )
  if (!list)
    return (
      <Panel title="Corrections" delay={0}>
        <Skeleton />
      </Panel>
    )
  if (list.total === 0)
    return (
      <Panel title="Corrections" delay={0}>
        <p className="text-ink-2">
          No hard-case pool yet. Build it with <code className="num">python -m docduel.datasets.hard</code>.
        </p>
      </Panel>
    )

  const setField = (k: string, v: string) => form && setForm({ ...form, fields: { ...form.fields, [k]: v } })
  const setRow = (i: number, k: keyof Row, v: string) =>
    form && setForm({ ...form, rows: form.rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)) })
  const share = list.verified / list.total

  return (
    <>
      <section className="surface rise rounded-xl px-5 py-5 sm:px-7" style={anim(0)}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-[680px]">
            <h1 className="font-serif text-[30px] leading-tight font-bold sm:text-[34px]">Corrections</h1>
            <p className="mt-2 text-[15px] text-ink-2">
              Check each answer from our model ({list.prefill_model}) against the page, fix anything wrong and save.
              Your verified answers become training data for round 2.
            </p>
          </div>
          <p className="num text-[15px]" aria-live="polite">
            <strong className="text-[22px]">{list.verified}</strong> of {list.total} verified
          </p>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-wash" aria-hidden="true">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-500"
            style={{ width: `${share * 100}%` }}
          />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-1.5" role="list" aria-label="Documents">
          {list.items.map((it, i) => (
            <button
              key={it.id}
              role="listitem"
              title={`${it.id}${it.verified ? " (verified)" : ""}`}
              aria-label={`Document ${i + 1}${it.verified ? ", verified" : ""}`}
              aria-current={it.id === current ? "true" : undefined}
              onClick={() => open(it.id)}
              className={cn(
                "size-3.5 rounded-full border transition-transform hover:scale-125",
                it.verified ? "border-sage bg-sage" : "border-line-2 bg-card-solid",
                it.id === current && "ring-2 ring-clay ring-offset-2 ring-offset-card",
              )}
            />
          ))}
        </div>
        {!list.prefill_ready && (
          <p className="mt-3 text-[14px] text-amber">
            No saved answers from {list.prefill_model} yet, so the form starts empty. Run the hard-correct eval first.
          </p>
        )}
      </section>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <section
          className="surface rise rounded-xl p-3 sm:p-4 lg:sticky lg:top-4"
          style={anim(80)}
          aria-label="Document"
        >
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-1">
              <IconBtn label="Previous document" onClick={() => go(-1)}>
                <ChevronLeft />
              </IconBtn>
              <span className="num px-1 text-[14px]">
                {current}{" "}
                <span className="text-ink-3">
                  ({index + 1}/{list.total})
                </span>
              </span>
              <IconBtn label="Next document" onClick={() => go(1)}>
                <ChevronRight />
              </IconBtn>
            </div>
            <div className="flex items-center gap-1">
              <IconBtn label="Zoom out" disabled={zoom === 0} onClick={() => setZoom(zoom - 1)}>
                <Minus />
              </IconBtn>
              <span className="num w-10 text-center text-[13px] text-ink-2">{ZOOMS[zoom] * 100}%</span>
              <IconBtn label="Zoom in" disabled={zoom === ZOOMS.length - 1} onClick={() => setZoom(zoom + 1)}>
                <Plus />
              </IconBtn>
            </div>
          </div>
          <div className="max-h-[calc(100vh-150px)] overflow-auto rounded-lg border border-line bg-white">
            {current && (
              <img
                key={current}
                src={correctionImageUrl(current)}
                alt={`Page image of ${current}`}
                style={{ width: `${ZOOMS[zoom] * 100}%`, maxWidth: "none" }}
                className="block"
              />
            )}
          </div>
        </section>

        <section className="surface rise rounded-xl px-5 py-5 sm:px-6" style={anim(140)} aria-label="Answer">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="font-serif text-[19px] font-semibold">Answer</h2>
            {doc && (
              <span className="text-[13px] text-ink-3">
                {doc.verified ? "Verified, you can still edit" : `Pre-filled by ${doc.prefill_model}`}
                {doc.prefill_valid ? "" : " (its answer was not valid JSON)"}
              </span>
            )}
          </div>
          {!loaded || !form || !prefill ? (
            <div className="mt-4">
              <Skeleton />
            </div>
          ) : (
            <form
              className="mt-4"
              onSubmit={(e) => {
                e.preventDefault()
                void save()
              }}
            >
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                {EXTRACT_FIELDS.map((d) => {
                  const changed = form.fields[d.key] !== prefill.fields[d.key]
                  return (
                    <label key={d.key} className={cn("block", d.key === "vendor_name" && "col-span-2")}>
                      <span className="mb-1 flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
                        {d.label}
                        {changed && (
                          <span className="size-1.5 rounded-full bg-clay" title="Changed from the pre-fill" />
                        )}
                      </span>
                      <input
                        value={form.fields[d.key]}
                        onChange={(e) => setField(d.key, e.target.value)}
                        inputMode={d.kind === "money" ? "decimal" : undefined}
                        placeholder={d.key === "document_date" ? "YYYY-MM-DD" : "blank if not shown"}
                        className={cn(
                          "h-9 w-full rounded-md border border-line-2 bg-card-solid px-3 placeholder:text-ink-3",
                          d.kind === "money" && "num",
                        )}
                      />
                    </label>
                  )
                })}
              </div>

              <div className="mt-5">
                <div className="mb-1.5 flex items-baseline justify-between">
                  <span className="text-[13px] font-medium text-ink-2">Line items</span>
                  <span className="text-[12px] text-ink-3">description, qty, unit price, amount</span>
                </div>
                <div className="space-y-1.5">
                  {form.rows.map((r, i) => (
                    <div
                      key={i}
                      className="grid grid-cols-[minmax(0,1fr)_40px_60px_66px_28px] sm:grid-cols-[minmax(0,1fr)_52px_78px_84px_28px] items-center gap-1.5"
                    >
                      <input
                        aria-label={`Line ${i + 1} description`}
                        value={r.description}
                        onChange={(e) => setRow(i, "description", e.target.value)}
                        className="h-8 min-w-0 rounded-md border border-line-2 bg-card-solid px-2 text-[14px]"
                      />
                      <input
                        aria-label={`Line ${i + 1} quantity`}
                        value={r.quantity}
                        onChange={(e) => setRow(i, "quantity", e.target.value)}
                        className="num h-8 min-w-0 rounded-md border border-line-2 bg-card-solid px-2 text-[14px]"
                      />
                      <input
                        aria-label={`Line ${i + 1} unit price`}
                        value={r.unit_price}
                        onChange={(e) => setRow(i, "unit_price", e.target.value)}
                        className="num h-8 min-w-0 rounded-md border border-line-2 bg-card-solid px-2 text-[14px]"
                      />
                      <input
                        aria-label={`Line ${i + 1} amount`}
                        value={r.amount}
                        onChange={(e) => setRow(i, "amount", e.target.value)}
                        className="num h-8 min-w-0 rounded-md border border-line-2 bg-card-solid px-2 text-[14px]"
                      />
                      <IconBtn
                        label={`Remove line ${i + 1}`}
                        onClick={() => setForm({ ...form, rows: form.rows.filter((_, j) => j !== i) })}
                      >
                        <Trash2 />
                      </IconBtn>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setForm({
                      ...form,
                      rows: [...form.rows, { description: "", quantity: "", unit_price: "", amount: "" }],
                    })
                  }
                  className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-[14px] text-primary hover:bg-wash"
                >
                  <Plus className="size-4" /> Add line
                </button>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                <span className="text-[13px] text-ink-2">
                  {edited === 0
                    ? "No changes from the pre-fill"
                    : `${edited} ${edited === 1 ? "change" : "changes"} from the pre-fill`}
                </span>
                <button
                  type="submit"
                  disabled={saving}
                  className="h-11 rounded-full bg-primary px-6 font-medium text-primary-foreground transition-[background-color,opacity,transform] hover:bg-primary-hover active:scale-[0.99] disabled:opacity-40"
                >
                  {saving ? "Saving" : "Save and next"}
                  <span className="ml-2 hidden text-[12px] opacity-70 sm:inline">Ctrl+Enter</span>
                </button>
              </div>
              {message && (
                <p className="mt-3 text-[14px] text-rust" role="status">
                  {message}
                </p>
              )}
            </form>
          )}
        </section>
      </div>
    </>
  )
}

function Panel({ title, delay, children }: { title: string; delay: number; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="surface rise rounded-xl px-5 py-5 sm:px-6" style={anim(delay)}>
      <h2 className="font-serif text-[19px] font-semibold">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Skeleton() {
  return (
    <div className="space-y-2.5" aria-hidden="true">
      {[80, 64, 72].map((w) => (
        <div key={w} className="h-3 animate-pulse rounded-full bg-wash" style={{ width: `${w}%` }} />
      ))}
    </div>
  )
}

function IconBtn({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex size-7 items-center justify-center rounded-md text-ink-2 hover:bg-wash hover:text-foreground disabled:opacity-30 [&_svg]:size-4"
    >
      {children}
    </button>
  )
}
