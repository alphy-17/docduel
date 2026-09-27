// Mirrors the backend contracts (Plan Section 9). Keep in sync with backend/src/docduel/schemas.

export type DocKind = "pdf_text" | "pdf_scan" | "image" | "csv"
export type Task = "extract" | "categorise" | "summarise" | "custom" | "describe"

export interface DocumentOut {
  document_id: string
  kind: DocKind
  pages: number
  text_preview: string
  ocr_ms: number
  is_test_document: boolean
  already_ingested: boolean
  can_describe: boolean
}

export interface LineItem {
  description: string
  quantity: number | null
  unit_price: number | null
  amount: number | null
}

export interface ReceiptExtraction {
  vendor_name: string | null
  document_date: string | null
  document_number: string | null
  currency: string | null
  line_items: LineItem[]
  subtotal: number | null
  tax: number | null
  service_charge: number | null
  discount: number | null
  total: number | null
  payment_method: string | null
}

export interface TransactionCategories {
  items: { row_id: number; category: string }[]
}

export interface SummaryOutput {
  bullets: string[]
}

export type ModelOutput = ReceiptExtraction | TransactionCategories | SummaryOutput | string

export interface Completed {
  model_key: string
  output: ModelOutput
  schema_valid: boolean | null
  ttft_ms: number | null
  latency_ms: number | null
  input_tokens: number
  output_tokens: number
  cost_usd: number | null
  cold_start: boolean
}

export interface ModelError {
  model_key: string
  error_code: string
  message: string
}

export interface RunStarted {
  run_id: string
  task: Task
  model_keys?: string[]
  placeholders?: string[]
  replayed?: boolean
}

export interface HealthModel {
  model_id: string | null
  status: string
  key_present: boolean
}

export interface ApiErrorBody {
  error_code: string
  message: string
}

// score.completed (Plan 5.5): only sent when the uploaded file is a frozen test document.
export interface ExtractTruth {
  fields: Record<string, boolean>
  expected: Record<string, unknown>
  correct_items: number[]
  items: { tp: number; pred: number; gold: number }
  field_accuracy: number | null
  line_item_f1: number
  perfect: boolean
}

export interface CategoriseTruth {
  rows: Record<string, boolean>
  expected: Record<string, string>
  accuracy: number | null
}

export interface ScoreCompleted {
  mode: "ground_truth"
  test_document_id: string
  results: Record<string, ExtractTruth | CategoriseTruth>
}

// GET /api/benchmark (Plan 5.6). Every number comes from reports/*.json (rule R5).
export interface Metric {
  value: number
  ci95: [number, number]
  display: string
}

export interface SpeedCost {
  latency_ms_p50: number | null
  latency_ms_p95: number | null
  cost_per_1000_docs_usd: number | null
  cost_usd_total: number
  // Our GPU model only: GPU busy time / documents with several requests in flight (Plan 11).
  steady_load?: { concurrency: number; wall_seconds: number; docs: number; cost_per_1000_docs_usd: number }
}

export interface Failure {
  id: string
  source: string
  valid: boolean
  fields: string
  wrong_fields: Record<string, { predicted: unknown; expected: unknown }>
  items: { tp: number; pred: number; gold: number }
  line_items: { predicted: LineItem[] | null; expected: LineItem[] } | null
}

export interface ExtractReport {
  created_at: string
  docs: number
  headline: Record<string, Metric | number>
  per_field: Record<string, { scored: number; accuracy: number; accuracy_exact: number }>
  worst_failures: Failure[]
  speed_cost: SpeedCost
  notes: string[]
}

export interface CategoriseReport {
  created_at: string
  docs: number
  rows: number
  headline: Record<string, Metric>
  confusion_matrix: Record<string, Record<string, number>>
  speed_cost: SpeedCost
}

export interface BenchmarkModel {
  model_id: string | null
  reasoning_effort: string | null
  status: string
  extract: ExtractReport | null
  categorise: CategoriseReport | null
}

export interface Benchmark {
  dataset_version: string
  prompt_version: string
  ours: string | null
  baseline: string
  relative_score: number | null
  models: Record<string, BenchmarkModel>
}
