import { useCallback, useEffect, useRef, useState } from "react"

import { ApiError, openRunStream, startRun, uploadDocument } from "@/lib/api"
import { parseCsv } from "@/lib/csv"
import type { Completed, DocumentOut, ModelError, ScoreCompleted, Task } from "@/lib/types"

export const MAX_BYTES = 10 * 1024 * 1024
export const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.csv"
const OK_TYPES = /\.(pdf|png|jpe?g|webp|csv)$/i
const TRANSACTIONS_HEADER = "row_id | date | description | amount"

export type PanelStatus = "idle" | "waiting" | "streaming" | "done" | "error"

export interface PanelState {
  key: string
  status: PanelStatus
  text: string
  startedAt: number
  completed?: Completed
  error?: ModelError
}

export type Phase = "empty" | "uploading" | "ready" | "running" | "done"

export function isTransactions(doc: DocumentOut | null): boolean {
  return !!doc && doc.kind === "csv" && doc.text_preview.startsWith(TRANSACTIONS_HEADER)
}

export function tasksFor(doc: DocumentOut | null): Record<Task, boolean> {
  const csv = doc?.kind === "csv"
  return {
    extract: !!doc && !csv,
    categorise: isTransactions(doc),
    summarise: !!doc,
    custom: !!doc,
    describe: !!doc?.can_describe,
  }
}

export function useDuel() {
  const [phase, setPhase] = useState<Phase>("empty")
  const [file, setFile] = useState<File | null>(null)
  const [doc, setDoc] = useState<DocumentOut | null>(null)
  const [task, setTask] = useState<Task>("extract")
  const [instructions, setInstructions] = useState("")
  const [notice, setNotice] = useState<string | null>(null)
  const [panels, setPanels] = useState<PanelState[]>([])
  const [placeholders, setPlaceholders] = useState<string[]>([])
  const [runTask, setRunTask] = useState<Task | null>(null)
  const [rowLabels, setRowLabels] = useState<string[]>([])
  // One page number for both panels, so the same rows line up side by side.
  const [page, setPage] = useState(0)
  // Ground-truth scores, only for frozen test documents (Plan 5.5). Null means agreement mode.
  const [truth, setTruth] = useState<ScoreCompleted | null>(null)
  const closeStream = useRef<(() => void) | null>(null)

  useEffect(() => () => closeStream.current?.(), [])

  const patch = useCallback((key: string, fn: (p: PanelState) => PanelState) => {
    setPanels((all) => all.map((p) => (p.key === key ? fn(p) : p)))
  }, [])

  const selectFile = useCallback(async (f: File) => {
    setNotice(null)
    if (!OK_TYPES.test(f.name)) {
      setNotice("That file type isn't supported. Use a PDF, PNG, JPEG, WEBP or CSV.")
      return
    }
    if (f.size > MAX_BYTES) {
      setNotice("That file is over 10 MB. Try a smaller scan or photo.")
      return
    }
    closeStream.current?.()
    setFile(f)
    setDoc(null)
    setRowLabels([])
    if (/\.csv$/i.test(f.name)) {
      // Keep each row's description so the categorise results can show it next to the row id.
      f.text().then((t) => {
        const rows = parseCsv(t)
        const col = rows[0]?.findIndex((h) => h.trim().toLowerCase() === "description") ?? -1
        if (col >= 0) setRowLabels(rows.slice(1).map((r) => r[col] ?? ""))
      })
    }
    setPanels([])
    setTruth(null)
    setPhase("uploading")
    try {
      const d = await uploadDocument(f)
      setDoc(d)
      const allowed = tasksFor(d)
      setTask(allowed.extract ? "extract" : allowed.categorise ? "categorise" : "summarise")
      setPhase("ready")
    } catch (e) {
      setFile(null)
      setPhase("empty")
      setNotice(e instanceof ApiError ? e.message : "Upload failed. Is the backend running?")
    }
  }, [])

  const clear = useCallback(() => {
    closeStream.current?.()
    setFile(null)
    setDoc(null)
    setPanels([])
    setTruth(null)
    setNotice(null)
    setPhase("empty")
  }, [])

  const run = useCallback(async () => {
    if (!doc) return
    setNotice(null)
    setPanels([])
    setPage(0)
    setTruth(null)
    setPhase("running")
    setRunTask(task)
    let runId: string
    try {
      runId = await startRun(doc.document_id, task, instructions.trim() || undefined)
    } catch (e) {
      setPhase("ready")
      setNotice(e instanceof ApiError ? e.message : "Could not start the run.")
      return
    }
    closeStream.current = openRunStream(runId, {
      onStarted: (e) => {
        const now = Date.now()
        setPlaceholders(e.placeholders ?? [])
        setPanels(
          (e.model_keys ?? []).map((key) => ({ key, status: "waiting", text: "", startedAt: now })),
        )
      },
      onDelta: (key, text) =>
        patch(key, (p) => ({ ...p, status: "streaming", text: p.text + text })),
      onCompleted: (c) => {
        setPanels((all) =>
          all.some((p) => p.key === c.model_key)
            ? all.map((p) => (p.key === c.model_key ? { ...p, status: "done", completed: c } : p))
            : [...all, { key: c.model_key, status: "done", text: "", startedAt: Date.now(), completed: c }],
        )
      },
      onError: (err) => {
        setPanels((all) =>
          all.some((p) => p.key === err.model_key)
            ? all.map((p) => (p.key === err.model_key ? { ...p, status: "error", error: err } : p))
            : [...all, { key: err.model_key, status: "error", text: "", startedAt: Date.now(), error: err }],
        )
      },
      onScore: setTruth,
      onDone: () => setPhase("done"),
      onConnectionLost: () => {
        setPhase("done")
        setNotice("Lost the connection to the server before the run finished.")
      },
    })
  }, [doc, task, instructions, patch])

  return {
    phase,
    file,
    doc,
    task,
    setTask,
    instructions,
    setInstructions,
    notice,
    panels,
    placeholders,
    runTask,
    rowLabels,
    page,
    setPage,
    truth,
    selectFile,
    clear,
    run,
  }
}
