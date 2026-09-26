"""Normalise money, quantities and strings for labels and scoring (Plan Section 10.1)."""

import re
from decimal import Decimal, InvalidOperation

_CURRENCY = re.compile(r"(?i)\b(rp|idr|aud|usd|nzd|gbp)\b\.?|rp\.?|[$£€@*]")


def parse_amount(value: object) -> Decimal | None:
    """Parse a money string written in either Indonesian or English style.

    A separator followed by exactly three digits is a thousands separator; one or two digits
    after the last separator make it a decimal point. So "25.000" and "25,000" are 25000,
    "1.250.500" is 1250500 and "12.50" is 12.5.
    """
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    s = str(value).strip()
    if not s:
        return None
    negative = s.startswith("-") or s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    s = _CURRENCY.sub("", s)
    s = re.sub(r"[^\d.,]", "", s)
    if not re.search(r"\d", s):
        return None
    groups = re.split(r"[.,]", s)
    if len(groups) == 1:
        number = groups[0]
    elif len(groups[-1]) in (1, 2):
        number = "".join(groups[:-1]) + "." + groups[-1]
    else:
        number = "".join(groups)
    try:
        result = Decimal(number or "0")
    except InvalidOperation:
        return None
    return -result if negative else result


def parse_quantity(value: object) -> Decimal | None:
    """'1X', 'x2', '3 x', '2Prs' -> the first number found."""
    if value is None:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", str(value))
    return Decimal(m.group().replace(",", ".")) if m else None


def to_float(d: Decimal | None) -> float | None:
    return None if d is None else float(d)


def normalise_text(value: str | None) -> str:
    """Case, whitespace and punctuation-insensitive form for short string fields."""
    if not value:
        return ""
    s = re.sub(r"[^\w\s]", " ", str(value).lower())
    return re.sub(r"\s+", " ", s).strip()
