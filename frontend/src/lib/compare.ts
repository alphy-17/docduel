import type { ReceiptExtraction, TransactionCategories } from "./types"

// Agreement between the two models (Plan 10.5). This is NOT accuracy: for documents outside
// the test set we do not know the right answer. Ground-truth scoring arrives in Phase 5.

export type Mark = "agree" | "differ" | "none"

export const EXTRACT_FIELDS: { key: keyof ReceiptExtraction; label: string; kind: "money" | "text" }[] = [
  { key: "vendor_name", label: "Vendor", kind: "text" },
  { key: "document_date", label: "Date", kind: "text" },
  { key: "document_number", label: "Number", kind: "text" },
  { key: "currency", label: "Currency", kind: "text" },
  { key: "subtotal", label: "Subtotal", kind: "money" },
  { key: "tax", label: "Tax", kind: "money" },
  { key: "service_charge", label: "Service charge", kind: "money" },
  { key: "discount", label: "Discount", kind: "money" },
  { key: "total", label: "Total", kind: "money" },
  { key: "payment_method", label: "Payment", kind: "text" },
]

const norm = (v: unknown) =>
  v === null || v === undefined
    ? null
    : String(v).toLowerCase().replace(/[^\p{L}\p{N}.]+/gu, " ").trim()

function same(a: unknown, b: unknown): boolean {
  if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) <= 0.01
  return norm(a) === norm(b)
}

export function markField(a: unknown, b: unknown): Mark {
  const empty = (v: unknown) => v === null || v === undefined || v === ""
  if (empty(a) && empty(b)) return "none"
  return same(a, b) ? "agree" : "differ"
}

export function extractAgreement(a: ReceiptExtraction, b: ReceiptExtraction) {
  let agree = 0
  let total = 0
  for (const f of EXTRACT_FIELDS) {
    const m = markField(a[f.key], b[f.key])
    if (m === "none") continue
    total += 1
    if (m === "agree") agree += 1
  }
  return { agree, total }
}

export function categoryAgreement(a: TransactionCategories, b: TransactionCategories) {
  const other = new Map(b.items.map((i) => [i.row_id, i.category]))
  const rows = new Set([...a.items.map((i) => i.row_id), ...b.items.map((i) => i.row_id)])
  let agree = 0
  for (const i of a.items) if (other.get(i.row_id) === i.category) agree += 1
  return { agree, total: rows.size }
}
