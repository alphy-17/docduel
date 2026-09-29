import type {
  ApiErrorBody,
  Benchmark,
  Completed,
  CorrectionDoc,
  CorrectionList,
  CorrectionSaved,
  DocumentOut,
  HealthModel,
  ModelError,
  ReceiptExtraction,
  RunStarted,
  Replay,
  ReplayIndex,
  ScoreCompleted,
  Task,
} from "./types"

/**
 * Plan 9.2/9.3. The public build (npm run build) is a replay demo: the Benchmark and the recorded
 * runs are static files in public/demo, so visitors never wait for a cold GPU or cost money.
 * Live mode (own uploads) calls the backend at VITE_API_BASE and needs the access code.
 * The dev server (npm run dev) stays fully live against the local backend.
 */
export const DEMO = import.meta.env.PROD
const API = `${import.meta.env.VITE_API_BASE ?? ""}/api`
const CODE_KEY = "docduel-access-code"

let accessCode = ""
try {
  accessCode = sessionStorage.getItem(CODE_KEY) ?? ""
} catch {
  // storage can be blocked; the visitor just types the code again
}
export const hasAccessCode = () => accessCode !== ""

const codeHeader = (): Record<string, string> => (accessCode ? { "X-Access-Code": accessCode } : {})

export class ApiError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

async function readJson<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body as ApiErrorBody | null
    throw new ApiError(err?.error_code ?? `http_${res.status}`, err?.message ?? "Something went wrong.")
  }
  return body as T
}

export async function getHealth(): Promise<Record<string, HealthModel>> {
  if (DEMO) {
    const idx = await getReplayIndex()
    return Object.fromEntries(
      Object.entries(idx.models).map(([k, m]) => [k, { model_id: m.model_id, status: "active", key_present: true }]),
    )
  }
  const res = await fetch(`${API}/health`)
  const body = await readJson<{ models: Record<string, HealthModel> }>(res)
  return body.models
}

export async function getBenchmark(): Promise<Benchmark> {
  return readJson<Benchmark>(await fetch(DEMO ? "/demo/benchmark.json" : `${API}/benchmark`))
}

export async function getCorrections(): Promise<CorrectionList> {
  return readJson<CorrectionList>(await fetch(`${API}/corrections`))
}

export async function getCorrection(id: string): Promise<CorrectionDoc> {
  return readJson<CorrectionDoc>(await fetch(`${API}/corrections/${encodeURIComponent(id)}`))
}

export const correctionImageUrl = (id: string) => `${API}/corrections/${encodeURIComponent(id)}/image`

export async function saveCorrection(id: string, answer: ReceiptExtraction): Promise<CorrectionSaved> {
  const res = await fetch(`${API}/corrections/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(answer),
  })
  return readJson<CorrectionSaved>(res)
}

export async function uploadDocument(file: File): Promise<DocumentOut> {
  const form = new FormData()
  form.append("file", file)
  return readJson<DocumentOut>(await fetch(`${API}/documents`, { method: "POST", headers: codeHeader(), body: form }))
}

export async function startRun(documentId: string, task: Task, instructions?: string): Promise<string> {
  const res = await fetch(`${API}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...codeHeader() },
    body: JSON.stringify({ document_id: documentId, task, instructions: instructions || null }),
  })
  return (await readJson<{ run_id: string }>(res)).run_id
}

export interface StreamHandlers {
  onStarted: (e: RunStarted) => void
  onDelta: (modelKey: string, text: string) => void
  onCompleted: (e: Completed) => void
  onError: (e: ModelError) => void
  onScore: (e: ScoreCompleted) => void
  onDone: () => void
  onConnectionLost: () => void
}

/**
 * Opens the live SSE stream for a run. EventSource is the browser's built-in SSE client:
 * one long-lived connection, the server pushes named events down it.
 */
export function openRunStream(runId: string, h: StreamHandlers): () => void {
  const es = new EventSource(`${API}/runs/${runId}/stream`)
  let finished = false
  const parse = (e: Event) => JSON.parse((e as MessageEvent).data)

  es.addEventListener("run.started", (e) => h.onStarted(parse(e)))
  es.addEventListener("model.delta", (e) => {
    const d = parse(e)
    h.onDelta(d.model_key, d.text)
  })
  es.addEventListener("model.completed", (e) => h.onCompleted(parse(e)))
  es.addEventListener("model.error", (e) => h.onError(parse(e)))
  es.addEventListener("score.completed", (e) => h.onScore(parse(e)))
  es.addEventListener("run.completed", () => {
    finished = true
    es.close()
    h.onDone()
  })
  // EventSource retries forever by default. We stop it and show a clear message instead.
  es.onerror = () => {
    if (!finished) {
      es.close()
      h.onConnectionLost()
    }
  }
  return () => es.close()
}

/** Checks the live-mode access code with the backend and keeps it for this browser tab. */
export async function unlockLive(code: string): Promise<void> {
  const res = await fetch(`${API}/access`, { method: "POST", headers: { "X-Access-Code": code.trim() } })
  if (!res.ok) await readJson(res)
  accessCode = code.trim()
  try {
    sessionStorage.setItem(CODE_KEY, accessCode)
  } catch {
    // fine: the code only lasts for this page load
  }
}

export type GpuState = "cold" | "waking" | "ready"

/** Asks the backend to wake the small model's GPU (if asleep) and returns its state. */
export async function getGpu(): Promise<GpuState> {
  return (await readJson<{ state: GpuState }>(await fetch(`${API}/gpu`, { headers: codeHeader() }))).state
}

/**
 * Live runs on the public site wait until the GPU answers: the hosting cuts requests after 240 s
 * and a cold GPU takes about 5 minutes. Polls only while waiting, so the GPU can still sleep later.
 */
export async function waitForGpu(onWaiting: () => void): Promise<void> {
  for (let i = 0; i < 60; i++) {
    if ((await getGpu()) === "ready") return
    if (i === 0) onWaiting()
    await new Promise((r) => setTimeout(r, 10_000))
  }
  throw new ApiError("gpu_timeout", "The small model's GPU didn't wake up. Try again in a few minutes.")
}

let replayIndex: Promise<ReplayIndex> | null = null
export function getReplayIndex(): Promise<ReplayIndex> {
  replayIndex ??= fetch("/demo/replays/index.json").then((r) => readJson<ReplayIndex>(r))
  return replayIndex
}

export async function getReplay(id: string): Promise<Replay> {
  return readJson<Replay>(await fetch(`/demo/replays/${encodeURIComponent(id)}.json`))
}

/** Plays a recorded run through the same handlers as the live stream, with its real timing. */
export function playReplay(replay: Replay, h: StreamHandlers): () => void {
  const timers = replay.events.map(({ t, event, data }) =>
    window.setTimeout(() => {
      const d = data as never
      if (event === "run.started") h.onStarted(d)
      else if (event === "model.delta")
        h.onDelta((data as { model_key: string }).model_key, (data as { text: string }).text)
      else if (event === "model.completed") h.onCompleted(d)
      else if (event === "model.error") h.onError(d)
      else if (event === "score.completed") h.onScore(d)
      else if (event === "run.completed") h.onDone()
    }, t),
  )
  return () => timers.forEach(clearTimeout)
}
