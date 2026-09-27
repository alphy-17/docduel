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
