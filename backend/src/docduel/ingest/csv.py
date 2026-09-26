"""CSV transactions: case-insensitive columns, row ids, clean prompt text."""

import io

import pandas as pd

from docduel.ingest.errors import IngestError
from docduel.ingest.limits import MAX_CSV_ROWS

REQUIRED = ("date", "description", "amount")


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise IngestError("csv_unreadable", "The CSV text encoding could not be read.")


def parse_transactions(data: bytes) -> pd.DataFrame:
    text = _decode(data)
    try:
        df = pd.read_csv(
            io.StringIO(text), dtype=str, keep_default_na=False, sep=None, engine="python"
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise IngestError("csv_unreadable", "The CSV could not be parsed.") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise IngestError(
            "csv_missing_columns",
            f"The CSV is missing required column(s): {', '.join(missing)}. "
            "It needs date, description and amount.",
        )
    df = df[list(REQUIRED)].map(lambda v: str(v).strip())
    df = df[(df != "").any(axis=1)].reset_index(drop=True)
    if df.empty:
        raise IngestError("csv_empty", "The CSV has no transaction rows.")
    if len(df) > MAX_CSV_ROWS:
        raise IngestError(
            "too_many_rows", f"The CSV has {len(df)} rows; the limit is {MAX_CSV_ROWS}."
        )
    df.insert(0, "row_id", range(1, len(df) + 1))
    return df


def render_for_prompt(df: pd.DataFrame) -> str:
    lines = ["row_id | date | description | amount"]
    lines += [f"{r.row_id} | {r.date} | {r.description} | {r.amount}" for r in df.itertuples()]
    return "\n".join(lines)
