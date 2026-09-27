const WHOLE_CURRENCIES = new Set(["IDR", "JPY", "KRW", "VND"])

export function money(value: number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined) return ""
  const digits = currency && WHOLE_CURRENCIES.has(currency.toUpperCase()) ? 0 : 2
  return value.toLocaleString("en-AU", { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function seconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return ""
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function usd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/a"
  if (value === 0) return "$0"
  if (value < 0.01) return `$${value.toPrecision(2)}`
  return `$${value.toFixed(2)}`
}

export function count(n: number): string {
  return n.toLocaleString("en-AU")
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
