import { useCallback, useEffect, useRef, useState } from "react"

import {
  ApiError,
  DEMO,
  getGpu,
  getReplay,
  getReplayIndex,
  hasAccessCode,
  openRunStream,
  playReplay,
  startRun,
  unlockLive,
  uploadDocument,
  waitForGpu,
  type StreamHandlers,
} from "@/lib/api"
import { parseCsv } from "@/lib/csv"
import type { Completed, DocumentOut, ModelError, ReplayEntry, ScoreCompleted, Task } from "@/lib/types"

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

export function tasksFor(doc: DocumentOut | null, replays?: ReplayEntry[] | null): Record<Task, boolean> {
  if (replays) {
    const has = (t: Task) => !!doc && replays.some((r) => r.task === t)
    return {
      extract: has("extract"),
      categorise: has("categorise"),
      summarise: has("summarise"),
      custom: false,
      describe: false,
    }
  }
  const csv = doc?.kind === "csv"
  return {
    extract: !!doc && !csv,
    categorise: isTransactions(doc),
    summarise: !!doc,
    custom: !!doc,
    describe: !!doc?.can_describe,
  }
}

/** "replay" plays recorded real runs (public default, D18); "live" calls the models. */
export type Mode = "replay" | "live"

export function useDuel() {
  const [mode, setMode] = useState<Mode>(DEMO && !hasAccessCode() ? "replay" : "live")
  // Replays recorded for the chosen sample (replay mode only).
  const [replays, setReplays] = useState<ReplayEntry[] | null>(null)
  const [phase, setPhase] = useState<Phase>("empty")
  // Public live mode only: true while the small model's GPU is starting up.
  const [gpuWaking, setGpuWaking] = useState(false)
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

  const selectFile = useCallback(
    async (f: File) => {
      setNotice(null)
      if (!OK_TYPES.test(f.name)) {
        setNotice("That file type isn't supported. Use a PDF, PNG, JPEG, WEBP or CSV.")
        return
      }
      if (f.size > MAX_BYTES) {
        setNotice("That file is over 10 MB. Try a smaller scan or photo.")
        return
      }
      let recorded: ReplayEntry[] = []
      if (mode === "replay") {
        recorded = (await getReplayIndex().catch(() => null))?.replays.filter((r) => r.sample === f.name) ?? []
        if (!recorded.length) {
          setNotice("Your own files use the live models. Enter the access code below, or try a sample.")
          return
        }
      }
      closeStream.current?.()
      setFile(f)
      setDoc(null)
      setReplays(null)
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
        const d = recorded.length ? (await getReplay(recorded[0].id)).document : await uploadDocument(f)
        setDoc(d)
        setReplays(recorded.length ? recorded : null)
        const allowed = tasksFor(d, recorded.length ? recorded : null)
        setTask(allowed.extract ? "extract" : allowed.categorise ? "categorise" : "summarise")
        setPhase("ready")
      } catch (e) {
        setFile(null)
        setPhase("empty")
        setNotice(e instanceof ApiError ? e.message : "Upload failed. Is the backend running?")
      }
    },
    [mode],
  )

  const clear = useCallback(() => {
    closeStream.current?.()
    setFile(null)
    setDoc(null)
    setReplays(null)
    setPanels([])
    setTruth(null)
    setNotice(null)
    setPhase("empty")
  }, [])

  const unlock = useCallback(async (code: string) => {
    await unlockLive(code) // throws ApiError with a readable message when the code is wrong
    if (DEMO) getGpu().catch(() => undefined) // start waking the GPU while the visitor picks a file
    closeStream.current?.()
    setMode("live")
    setFile(null)
    setDoc(null)
    setReplays(null)
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
    const handlers: StreamHandlers = {
      onStarted: (e) => {
        const now = Date.now()
        setPlaceholders(e.placeholders ?? [])
        setPanels((e.model_keys ?? []).map((key) => ({ key, status: "waiting", text: "", startedAt: now })))
      },
      onDelta: (key, text) => patch(key, (p) => ({ ...p, status: "streaming", text: p.text + text })),
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
    }
    try {
      if (replays) {
        const entry = replays.find((r) => r.task === task)
        if (!entry) throw new ApiError("no_replay", "There is no recorded run for this task.")
        closeStream.current = playReplay(await getReplay(entry.id), handlers)
        return
      }
      if (DEMO) {
        await waitForGpu(() => setGpuWaking(true))
        setGpuWaking(false)
      }
      const runId = await startRun(doc.document_id, task, instructions.trim() || undefined)
      closeStream.current = openRunStream(runId, handlers)
    } catch (e) {
      setGpuWaking(false)
      setPhase("ready")
      setNotice(e instanceof ApiError ? e.message : "Could not start the run.")
    }
  }, [doc, task, instructions, patch, replays])

  return {
    mode,
    replays,
    gpuWaking,
    unlock,
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
