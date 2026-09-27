// Small CSV reader for the preview only (the backend does the real parsing).
export function parseCsv(text: string, maxRows = 200): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ""
  let quoted = false
  const delimiter = text.split("\n", 1)[0].includes(";") && !text.split("\n", 1)[0].includes(",") ? ";" : ","
  for (let i = 0; i < text.length && rows.length <= maxRows; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"'
        i++
      } else if (ch === '"') quoted = false
      else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === delimiter) {
      row.push(cell.trim())
      cell = ""
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++
      row.push(cell.trim())
      cell = ""
      if (row.some((c) => c !== "")) rows.push(row)
      row = []
    } else cell += ch
  }
  if (cell !== "" || row.length) {
    row.push(cell.trim())
    if (row.some((c) => c !== "")) rows.push(row)
  }
  return rows
}
