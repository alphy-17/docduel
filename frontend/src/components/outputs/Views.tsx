import { EXTRACT_FIELDS, markField, type Mark } from "@/lib/compare"
import { money } from "@/lib/format"
import type {
  CategoriseTruth,
  ExtractTruth,
  ReceiptExtraction,
  SummaryOutput,
  TransactionCategories,
} from "@/lib/types"
import { cn } from "@/lib/utils"

const rowTone: Record<Mark, string> = {
  agree: "[&>td:last-child]:font-semibold [&>td:last-child]:text-sage",
  differ: "bg-amber-bg [&>td:last-child]:font-semibold [&>td:last-child]:text-amber",
  right: "[&>td:last-child]:font-semibold [&>td:last-child]:text-sage",
  wrong: "bg-rust-bg [&>td:last-child]:font-semibold [&>td:last-child]:text-rust",
  none: "",
}

function shownValue(v: unknown, kind: "money" | "text", currency: string | null): string | null {
  if (v === null || v === undefined) return null
  return kind === "money" ? money(v as number, currency) : String(v)
}

export function ExtractView({
  out,
  other,
  truth,
}: {
  out: ReceiptExtraction
  other?: ReceiptExtraction
  truth?: ExtractTruth
}) {
  const rows = EXTRACT_FIELDS.filter(
    (f) => out[f.key] !== null || (other && other[f.key] !== null) || (truth && f.key in truth.fields),
  )
  const correct = new Set(truth?.correct_items ?? [])
  return (
    <>
      <table className="w-full border-separate border-spacing-0">
        <tbody>
          {rows.map((f) => {
            const v = out[f.key]
            const scored = truth && f.key in truth.fields
            const mark: Mark = truth
              ? scored
                ? truth.fields[f.key]
                  ? "right"
                  : "wrong"
                : "none"
              : other
                ? markField(v, other[f.key])
                : "none"
            const shown = shownValue(v, f.kind, out.currency)
            const expected = mark === "wrong" ? shownValue(truth!.expected[f.key], f.kind, out.currency) : null
            return (
              <tr key={f.key} className={cn(rowTone[mark], "[&>td]:border-t [&>td]:border-line")}>
                <td className="w-[42%] rounded-l-md py-2.5 pl-2.5 text-ink-2">{f.label}</td>
                <td
                  className={cn(
                    "rounded-r-md py-2.5 pr-2.5 text-right",
                    f.kind === "money" && "num",
                    shown === null && "text-ink-3",
                  )}
                >
                  {shown ?? "not found"}
                  {expected !== null && (
                    <span className="block text-xs font-normal text-ink-2">should be {expected}</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {out.line_items.length > 0 && (
        <div className="mt-3 rounded-md bg-wash p-3 text-[13px]">
          <p className="eyebrow mb-1.5">
            {out.line_items.length} item{out.line_items.length > 1 ? "s" : ""}
            {truth && (
              <span className="normal-case tracking-normal">
                {" "}
                · {truth.items.tp} of {truth.items.gold} priced items right
              </span>
            )}
          </p>
          <ul className="space-y-1">
            {out.line_items.map((it, i) => (
              <li
                key={i}
                className={cn(
                  "flex gap-3",
                  truth && (correct.has(i) ? "[&>span:last-child]:font-semibold [&>span:last-child]:text-sage" : "text-rust"),
                )}
              >
                <span className="min-w-0 flex-1 truncate" title={it.description}>
                  {it.quantity && it.quantity !== 1 ? <span className="text-ink-3">{it.quantity} x </span> : null}
                  {it.description}
                </span>
                <span className="num shrink-0">{money(it.amount, out.currency)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}

export const PAGE_SIZE = 10

export function CategoriesView({
  out,
  other,
  labels = [],
  page = 0,
  truth,
}: {
  out: TransactionCategories
  other?: TransactionCategories
  labels?: string[]
  page?: number
  truth?: CategoriseTruth
}) {
  const theirs = new Map(other?.items.map((i) => [i.row_id, i.category]))
  const rows = out.items.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
  return (
    <table className="w-full table-fixed border-separate border-spacing-0 text-[13px]">
      <thead>
        <tr className="text-left text-xs text-ink-3">
          <th className="w-12 pb-1.5 pl-2.5 font-normal">Row</th>
          {labels.length > 0 && <th className="pb-1.5 font-normal">Description</th>}
          <th className="w-[36%] pb-1.5 font-normal">Category</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((i) => {
          const key = String(i.row_id)
          const mark: Mark = truth
            ? truth.rows[key]
              ? "right"
              : "wrong"
            : !other
              ? "none"
              : theirs.get(i.row_id) === i.category
                ? "agree"
                : "differ"
          return (
            <tr key={i.row_id} className={cn("[&>td]:border-t [&>td]:border-line", rowTone[mark])}>
              <td className="num rounded-l-md py-2 pl-2.5 text-ink-3">{i.row_id}</td>
              {labels.length > 0 && (
                <td className="truncate py-2 pr-3 text-ink-2" title={labels[i.row_id - 1]}>
                  {labels[i.row_id - 1]}
                </td>
              )}
              <td className="rounded-r-md py-2 pr-2.5">
                {i.category}
                {mark === "wrong" && truth?.expected[key] && (
                  <span className="block text-xs font-normal text-ink-2">should be {truth.expected[key]}</span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

/** "1-10 of 135" with Previous / Next. Shared by both panels so their rows stay aligned. */
export function Pager({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  if (total <= PAGE_SIZE) return null
  const last = Math.ceil(total / PAGE_SIZE) - 1
  const from = page * PAGE_SIZE + 1
  const to = Math.min(total, from + PAGE_SIZE - 1)
  const btn =
    "rounded-full border border-line-2 bg-card-solid px-3.5 py-1.5 text-[13px] font-medium transition-colors hover:border-ink-3 disabled:opacity-40 disabled:hover:border-line-2"
  return (
    <nav aria-label="Rows" className="mt-4 flex items-center justify-between gap-3">
      <span className="num text-xs text-ink-2" aria-live="polite">
        {from}-{to} of {total}
      </span>
      <span className="flex gap-2">
        <button type="button" className={btn} disabled={page === 0} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <button type="button" className={btn} disabled={page >= last} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </span>
    </nav>
  )
}

export function BulletsView({ out }: { out: SummaryOutput }) {
  return (
    <ul className="space-y-2.5">
      {out.bullets.map((b, i) => (
        <li key={i} className="flex gap-3">
          <span className="num mt-0.5 text-xs text-ink-3">{i + 1}</span>
          <span>{b}</span>
        </li>
      ))}
    </ul>
  )
}

export function TextView({ text }: { text: string }) {
  return (
    <div className="space-y-3 leading-relaxed">
      {text
        .split(/\n{2,}/)
        .filter(Boolean)
        .map((para, i) => (
          <p key={i}>{para}</p>
        ))}
    </div>
  )
}
