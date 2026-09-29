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
  ScoreCompleted,
  Task,
} from "./types"

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
  const res = await fetch("/api/health")
  const body = await readJson<{ models: Record<string, HealthModel> }>(res)
  return body.models
}

export async function getBenchmark(): Promise<Benchmark> {
  return readJson<Benchmark>(await fetch("/api/benchmark"))
}

export async function getCorrections(): Promise<CorrectionList> {
  return readJson<CorrectionList>(await fetch("/api/corrections"))
}

export async function getCorrection(id: string): Promise<CorrectionDoc> {
  return readJson<CorrectionDoc>(await fetch(`/api/corrections/${encodeURIComponent(id)}`))
}

export const correctionImageUrl = (id: string) => `/api/corrections/${encodeURIComponent(id)}/image`

export async function saveCorrection(id: string, answer: ReceiptExtraction): Promise<CorrectionSaved> {
  const res = await fetch(`/api/corrections/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(answer),
  })
  return readJson<CorrectionSaved>(res)
}

export async function uploadDocument(file: File): Promise<DocumentOut> {
  const form = new FormData()
  form.append("file", file)
  return readJson<DocumentOut>(await fetch("/api/documents", { method: "POST", body: form }))
}

export async function startRun(documentId: string, task: Task, instructions?: string): Promise<string> {
  const res = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  const es = new EventSource(`/api/runs/${runId}/stream`)
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
