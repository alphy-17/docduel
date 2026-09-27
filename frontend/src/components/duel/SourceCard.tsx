import { FileSpreadsheet, FileText, Upload } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { ACCEPT, tasksFor, type Phase } from "@/hooks/useDuel"
import { parseCsv } from "@/lib/csv"
import { fileSize, seconds } from "@/lib/format"
import type { DocumentOut, Task } from "@/lib/types"
import { cn } from "@/lib/utils"

import { useTypewriter } from "@/hooks/useTypewriter"

import { Typed } from "./TypeText"

const TASKS: { id: Task; name: string; hint: string; scored: boolean }[] = [
  { id: "extract", name: "Extract", hint: "Fields and items", scored: true },
  { id: "categorise", name: "Categorise", hint: "Bank transactions", scored: true },
  { id: "summarise", name: "Summarise", hint: "Three bullet points", scored: false },
  { id: "custom", name: "Ask", hint: "Your own question", scored: false },
  { id: "describe", name: "Describe", hint: "The image itself", scored: false },
]

const KIND_LABEL: Record<DocumentOut["kind"], string> = {
  pdf_text: "PDF with text",
  pdf_scan: "Scanned PDF",
  image: "Photo",
  csv: "CSV",
}

interface Props {
  phase: Phase
  file: File | null
  doc: DocumentOut | null
  task: Task
  instructions: string
  notice: string | null
  onFile: (f: File) => void
  onClear: () => void
  onTask: (t: Task) => void
  onInstructions: (s: string) => void
  onRun: () => void
}

/** The top section from the Owner's wireframe: Text | Document upload | Config options. */
export function SourceCard(p: Props) {
  const busy = p.phase === "uploading" || p.phase === "running"
  const allowed = tasksFor(p.doc)
  const needsInstructions = p.task === "custom" && !p.instructions.trim()
  const visibleTasks = TASKS.filter((t) => t.id !== "describe" || allowed.describe)
  const box = "inner rounded-lg border border-line-2 p-5"

  return (
    <section aria-label="Document and settings" className="surface rise rounded-xl p-3 sm:p-4" style={{ ["--d" as string]: "80ms" }}>
      <div className="grid gap-3 sm:gap-4 lg:grid-cols-3">
        {/* Text */}
        <IntroText box={box} />

        {/* Document upload */}
        <div className={box}>
          <h2 className="mb-3 font-serif text-[19px] font-semibold">Document</h2>
          {p.file ? (
            <DocumentRow file={p.file} doc={p.doc} uploading={p.phase === "uploading"} onClear={p.onClear} disabled={busy} />
          ) : (
            <>
              <Dropzone onFile={p.onFile} />
              <Samples onFile={p.onFile} />
            </>
          )}
          {p.notice && (
            <p role="alert" className="mt-3 rounded-md bg-rust-bg px-3 py-2 text-[13px] text-rust">
              {p.notice}
            </p>
          )}
          {p.doc && <Preview key={p.doc.document_id} file={p.file} doc={p.doc} />}
        </div>

        {/* Config options */}
        <div className={box}>
          <fieldset disabled={!p.doc || busy}>
            <legend className="mb-3 font-serif text-[19px] font-semibold">Task</legend>
            <div className="grid grid-cols-2 gap-2">
              {visibleTasks.map((t) => {
                const on = p.task === t.id
                const ok = !!p.doc && allowed[t.id]
                return (
                  <button
                    key={t.id}
                    type="button"
                    disabled={!ok}
                    aria-pressed={on}
                    onClick={() => p.onTask(t.id)}
                    title={ok || !p.doc ? undefined : t.id === "categorise" ? "Needs a CSV with date, description and amount" : "Not available for this file"}
                    className={cn(
                      "rounded-md border border-line-2 bg-card-solid px-3 py-2 text-left transition-colors",
                      on && p.doc && "border-primary shadow-[inset_0_0_0_1px_var(--primary)]",
                      !ok && "cursor-not-allowed opacity-45",
                      ok && !on && "hover:border-ink-3",
                    )}
                  >
                    <span className="block font-medium">{t.name}</span>
                    <span className="block text-xs text-ink-3">{t.hint}</span>
                  </button>
                )
              })}
            </div>

            <label className="mt-4 block">
              <span className="mb-1.5 block font-medium">
                {p.task === "custom" ? "Your question" : "Instructions"}{" "}
                {p.task !== "custom" && <span className="font-normal text-ink-3">(optional)</span>}
              </span>
              <textarea
                value={p.instructions}
                onChange={(e) => p.onInstructions(e.target.value)}
                maxLength={2000}
                rows={2}
                placeholder={p.task === "custom" ? "For example: when is this invoice due?" : "Anything the models should pay attention to"}
                className="w-full resize-y rounded-md border border-line-2 bg-card-solid px-3 py-2 placeholder:text-ink-3"
              />
            </label>
          </fieldset>

          <button
            type="button"
            onClick={p.onRun}
            disabled={!p.doc || busy || needsInstructions}
            className="mt-4 h-11 w-full rounded-full bg-primary font-medium text-primary-foreground transition-[background-color,opacity,transform] hover:bg-primary-hover active:scale-[0.99] disabled:opacity-40 disabled:hover:bg-primary"
          >
            {p.phase === "running" ? "Running both models…" : "Run both models"}
          </button>
          <p className="mt-2 text-center text-xs text-ink-3">
            {!p.doc ? "Add a document first." : needsInstructions ? "Type a question first." : "Usually a few seconds. Well under a cent."}
          </p>
        </div>
      </div>
    </section>
  )
}

const SAMPLES = [
  { file: "cafe-receipt.png", label: "Café receipt", kind: "Photo", type: "image/png" },
  { file: "scanned-receipt.pdf", label: "Scanned receipt", kind: "Scan", type: "application/pdf" },
  { file: "tax-invoice.pdf", label: "Tax invoice", kind: "PDF", type: "application/pdf" },
  { file: "bank-transactions.csv", label: "Bank transactions", kind: "CSV", type: "text/csv" },
]

/** Task 4.9: one-click sample documents, so visitors don't need their own files. */
function Samples({ onFile }: { onFile: (f: File) => void }) {
  const [loading, setLoading] = useState<string | null>(null)
  const pick = async (s: (typeof SAMPLES)[number]) => {
    setLoading(s.file)
    try {
      const blob = await (await fetch(`/samples/${s.file}`)).blob()
      onFile(new File([blob], s.file, { type: s.type }))
    } finally {
      setLoading(null)
    }
  }
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs text-ink-3">No file handy? Try a sample:</p>
      <div className="flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <button
            key={s.file}
            type="button"
            disabled={loading !== null}
            onClick={() => pick(s)}
            className="rounded-full border border-line-2 bg-card-solid px-3 py-1.5 text-[13px] transition-colors hover:border-ink-3 disabled:opacity-50"
          >
            {s.label} <span className="text-ink-3">{s.kind}</span>
          </button>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-ink-3">
        The café receipt is from the CORD dataset (CC BY 4.0). The others are synthetic.
      </p>
    </div>
  )
}

function Dropzone({ onFile }: { onFile: (f: File) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const f = e.dataTransfer.files[0]
        if (f) onFile(f)
      }}
      className={cn(
        "rounded-lg border border-dashed border-line-2 bg-card-solid px-5 py-8 text-center transition-colors",
        over && "border-foreground bg-wash",
      )}
    >
      <Upload className="mx-auto mb-3 size-5 text-ink-3" aria-hidden="true" />
      <p className="font-medium">Drop a file here</p>
      <p className="mt-1 text-xs text-ink-3">PDF, photo or CSV, up to 10 MB and 3 pages</p>
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="mt-4 rounded-full bg-secondary-btn px-5 py-2 font-medium text-white transition-colors hover:bg-secondary-btn-hover"
      >
        Choose file
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose a document to upload"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
          e.target.value = ""
        }}
      />
    </div>
  )
}

function useObjectUrl(file: File | null, enabled: boolean) {
  const url = useMemo(() => (file && enabled ? URL.createObjectURL(file) : null), [file, enabled])
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url)
  }, [url])
  return url
}

function DocumentRow(props: { file: File; doc: DocumentOut | null; uploading: boolean; disabled: boolean; onClear: () => void }) {
  const isImage = /\.(png|jpe?g|webp)$/i.test(props.file.name)
  const url = useObjectUrl(props.file, isImage)
  const Icon = /\.csv$/i.test(props.file.name) ? FileSpreadsheet : FileText
  const d = props.doc
  const meta = props.uploading
    ? "Reading the document…"
    : d
      ? [KIND_LABEL[d.kind], d.kind === "csv" ? null : `${d.pages} page${d.pages > 1 ? "s" : ""}`, d.ocr_ms ? `text read in ${seconds(d.ocr_ms)}` : null]
          .filter(Boolean)
          .join(", ")
      : fileSize(props.file.size)

  return (
    <div className="flex items-center gap-3.5 rounded-lg border border-line bg-card-solid p-3">
      <div className="grid h-[72px] w-[54px] shrink-0 place-items-center overflow-hidden rounded-sm border border-line bg-wash">
        {url ? <img src={url} alt="" className="h-full w-full object-cover" /> : <Icon className="size-5 text-ink-3" aria-hidden="true" />}
      </div>
      <div className="min-w-0">
        <p className="truncate font-medium" title={props.file.name}>
          {props.file.name}
        </p>
        <p className="text-xs text-ink-3" aria-live="polite">
          {meta}
        </p>
        {d?.is_test_document && (
          <p className="mt-1 inline-block rounded-full bg-sage-bg px-2 text-[11px] text-sage">In the test set</p>
        )}
      </div>
      <button
        type="button"
        disabled={props.disabled}
        onClick={props.onClear}
        className="ml-auto shrink-0 text-xs text-ink-2 underline underline-offset-4 disabled:opacity-40"
      >
        Change
      </button>
    </div>
  )
}

function Preview({ file, doc }: { file: File | null; doc: DocumentOut }) {
  const [rows, setRows] = useState<string[][] | null>(null)
  useEffect(() => {
    let live = true
    if (file && doc.kind === "csv") file.text().then((t) => live && setRows(parseCsv(t, 10)))
    return () => {
      live = false
    }
  }, [file, doc.kind])

  return (
    <details className="group mt-3 rounded-lg border border-line bg-card-solid">
      <summary className="cursor-pointer list-none px-3 py-2.5 text-[13px] font-medium text-ink-2 select-none">
        <span className="group-open:hidden">Show what the models will read</span>
        <span className="hidden group-open:inline">Hide</span>
      </summary>
      <div className="max-h-64 overflow-auto border-t border-line px-3 py-2.5">
        {rows ? (
          <table className="w-full text-xs">
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={i === 0 ? "font-medium" : "text-ink-2"}>
                  {r.map((c, j) => (
                    <td key={j} className="border-b border-line px-1.5 py-1 whitespace-nowrap">
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <pre className="num text-xs whitespace-pre-wrap text-ink-2">{doc.text_preview}</pre>
        )}
      </div>
    </details>
  )
}

const INTRO = {
  title: "Same document, two models.",
  lead: "DocDuel is a test bench for one question: can a small open model, trained on receipts and invoices, read them as well as OpenAI does, for a fraction of the cost?",
  steps: [
    "Upload a receipt, invoice, photo or bank CSV.",
    "Both models get the identical prompt at the same moment.",
    "Compare their answers field by field, with speed and cost per 1,000 documents.",
  ],
  note: "Extract and Categorise can be checked against an answer key. Summarise, Ask and Describe are for reading side by side.",
}
const BLOCKS = [INTRO.title, INTRO.lead, ...INTRO.steps, INTRO.note]
const OFFSETS = BLOCKS.map((_, i) => BLOCKS.slice(0, i).reduce((n, b) => n + b.length, 0))

function IntroText({ box }: { box: string }) {
  const shown = useTypewriter(BLOCKS)
  const at = (i: number) => <Typed text={BLOCKS[i]} offset={OFFSETS[i]} shown={shown} />
  const full = BLOCKS.join(" ")
  return (
    <div className={cn(box, "flex flex-col")}>
      <p className="sr-only">{full}</p>
      <div aria-hidden="true" className="flex flex-1 flex-col">
        <h1 className="mb-3 font-serif text-[30px] leading-[1.15] font-semibold tracking-tight">{at(0)}</h1>
        <p className="text-ink-2">{at(1)}</p>
        <ol className="mt-4 space-y-2">
          {INTRO.steps.map((_, i) => (
            <li key={i} className="flex gap-3">
              <span
                className="num mt-px grid size-5 shrink-0 place-items-center rounded-full bg-wash text-[11px] text-ink-2 transition-opacity duration-300"
                style={{ opacity: shown > OFFSETS[2 + i] ? 1 : 0 }}
              >
                {i + 1}
              </span>
              <span>{at(2 + i)}</span>
            </li>
          ))}
        </ol>
        <p className="mt-auto pt-4 text-xs text-ink-3">{at(BLOCKS.length - 1)}</p>
      </div>
    </div>
  )
}
