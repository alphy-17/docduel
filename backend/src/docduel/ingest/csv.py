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


TRANSACTIONS_HEADER = "row_id | date | description | amount"


def _read(data: bytes) -> pd.DataFrame:
    text = _decode(data)
    try:
        df = pd.read_csv(
            io.StringIO(text), dtype=str, keep_default_na=False, sep=None, engine="python"
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise IngestError("csv_unreadable", "The CSV could not be parsed.") from exc
    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_transactions(data: bytes) -> pd.DataFrame:
    """Strict: needs date, description and amount (used by categorise)."""
    df = _read(data)
    df.columns = [c.lower() for c in df.columns]
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
    lines = [TRANSACTIONS_HEADER]
    lines += [f"{r.row_id} | {r.date} | {r.description} | {r.amount}" for r in df.itertuples()]
    return "\n".join(lines)


def parse_table(data: bytes) -> pd.DataFrame:
    """Any CSV with a header row (used by summarise and custom, Plan 3.9)."""
    df = _read(data).map(lambda v: str(v).strip())
    df = df[(df != "").any(axis=1)].reset_index(drop=True)
    if df.empty or not len(df.columns):
        raise IngestError("csv_empty", "The CSV has no data rows.")
    if len(df) > MAX_CSV_ROWS:
        raise IngestError(
            "too_many_rows", f"The CSV has {len(df)} rows; the limit is {MAX_CSV_ROWS}."
        )
    return df


def render_table(df: pd.DataFrame) -> str:
    lines = [" | ".join(df.columns)]
    lines += [" | ".join(str(v) for v in row) for row in df.itertuples(index=False)]
    return "\n".join(lines)


def is_transactions_text(text: str) -> bool:
    """True when the stored CSV text came from a transactions file (categorise allowed)."""
    return text.startswith(TRANSACTIONS_HEADER + "\n") or text == TRANSACTIONS_HEADER
