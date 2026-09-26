"""Seeded synthetic bank-transaction CSVs with messy descriptors and known categories.

  uv run --group data python -m docduel.datasets.transactions

Training/dev rows use TRAIN_MERCHANTS; the frozen test set uses HELD_OUT_MERCHANTS only.
The two lists never overlap (checked by tests and by the leakage check).
"""

import csv
import io
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from docduel.settings import get_settings

SEED = 20260926

# category -> [(merchant name, low amount, high amount)]
TRAIN_MERCHANTS: dict[str, list[tuple[str, float, float]]] = {
    "Groceries": [
        ("WOOLWORTHS", 15, 220),
        ("COLES", 12, 200),
        ("ALDI STORES", 10, 150),
        ("IGA", 8, 90),
        ("HARRIS FARM MARKETS", 20, 120),
        ("FOODWORKS", 6, 60),
    ],
    "Dining": [
        ("MCDONALDS", 6, 30),
        ("GUZMAN Y GOMEZ", 12, 40),
        ("BLUE FIG CAFE", 5, 35),
        ("DOMINOS PIZZA", 12, 45),
        ("UBER *EATS", 18, 70),
        ("GRILLD", 18, 50),
    ],
    "Transport": [
        ("MYKI TOPUP", 10, 50),
        ("UBER *TRIP", 9, 60),
        ("SHELL COLES EXPRESS", 40, 110),
        ("AMPOL", 35, 100),
        ("CITYLINK", 8, 40),
        ("SECURE PARKING", 6, 35),
    ],
    "Utilities": [
        ("ORIGIN ENERGY", 80, 320),
        ("AGL", 70, 300),
        ("TELSTRA", 60, 130),
        ("OPTUS BILLING", 45, 110),
        ("YARRA VALLEY WATER", 60, 200),
    ],
    "Shopping": [
        ("KMART", 10, 120),
        ("BUNNINGS", 12, 250),
        ("JB HI-FI", 30, 900),
        ("TARGET", 15, 150),
        ("AMAZON AU", 10, 300),
        ("OFFICEWORKS", 8, 400),
    ],
    "Health": [
        ("CHEMIST WAREHOUSE", 8, 90),
        ("PRICELINE PHARMACY", 10, 80),
        ("SPECSAVERS", 60, 400),
        ("GEELONG DENTAL", 90, 450),
        ("BUPA", 80, 250),
    ],
    "Entertainment": [
        ("NETFLIX.COM", 11, 26),
        ("SPOTIFY", 12, 24),
        ("HOYTS", 16, 60),
        ("TICKETEK", 40, 250),
        ("STEAM GAMES", 10, 90),
    ],
    "Other": [
        ("ATM WITHDRAWAL", 20, 300),
        ("TRANSFER TO", 20, 800),
        ("ACCOUNT FEE", 2, 10),
        ("ATO PAYMENT", 100, 1500),
        ("CHARITY DONATION", 10, 100),
    ],
}
HELD_OUT_MERCHANTS: dict[str, list[tuple[str, float, float]]] = {
    "Groceries": [
        ("DRAKES SUPERMARKET", 15, 180),
        ("SPUDSHED", 10, 90),
        ("COSTCO WHOLESALE", 60, 400),
    ],
    "Dining": [
        ("NANDOS", 14, 45),
        ("HUNGRY JACKS", 6, 25),
        ("MENULOG", 20, 70),
        ("BOOST JUICE", 7, 14),
    ],
    "Transport": [
        ("OPAL TRAVEL", 5, 40),
        ("BP CONNECT", 40, 110),
        ("DIDI MOBILITY", 8, 50),
        ("WILSON PARKING", 8, 40),
    ],
    "Utilities": [
        ("ENERGYAUSTRALIA", 90, 300),
        ("RED ENERGY", 70, 260),
        ("AUSSIE BROADBAND", 60, 100),
    ],
    "Shopping": [
        ("MYER", 20, 300),
        ("BIG W", 10, 120),
        ("THE GOOD GUYS", 50, 1200),
        ("IKEA", 20, 500),
    ],
    "Health": [
        ("TERRYWHITE CHEMMART", 8, 70),
        ("MEDIBANK", 90, 260),
        ("PHYSIO PLUS CLINIC", 70, 140),
    ],
    "Entertainment": [("DISNEY PLUS", 12, 20), ("VILLAGE CINEMAS", 16, 60), ("TIMEZONE", 10, 80)],
    "Other": [("BPAY PAYMENT", 30, 600), ("INTL TXN FEE", 1, 8), ("RENT TRANSFER", 300, 900)],
}
PLACES = [
    "GEELONG",
    "MELBOURNE",
    "BELMONT",
    "WAURN PONDS",
    "BALLARAT",
    "SYDNEY",
    "TORQUAY",
    "BRUNSWICK",
    "CARLTON",
    "DOCKLANDS",
]


def merchant_names(table: dict[str, list[tuple[str, float, float]]]) -> set[str]:
    return {m for rows in table.values() for m, *_ in rows}


def _descriptor(rng: random.Random, merchant: str) -> str:
    """Messy bank-statement style text, e.g. 'SQ *BLUE FIG CAFE 4411 GEELONG AU'."""
    if merchant in ("ATM WITHDRAWAL", "ACCOUNT FEE", "INTL TXN FEE", "BPAY PAYMENT", "ATO PAYMENT"):
        return f"{merchant} {rng.randint(1000, 9999)}"
    if merchant in ("TRANSFER TO", "RENT TRANSFER"):
        payee = rng.choice(["SAVINGS", "J SMITH", "LANDLORD", "ACC 1234"])
        return f"{merchant} {payee} REF{rng.randint(100, 999)}"
    prefix = rng.choice(["", "", "SQ *", "EFTPOS ", "VISA PURCHASE ", "PAYPAL *", "POS ", "CARD "])
    body = merchant if not prefix.endswith("*") else merchant.replace(" ", "")[:18]
    store = rng.choice(["", f" {rng.randint(100, 9999)}", f" #{rng.randint(10, 999)}"])
    place = rng.choice(["", f" {rng.choice(PLACES)}", f" {rng.choice(PLACES)} AU", " AUS"])
    tail = rng.choice(
        [
            "",
            "",
            f" CARD {rng.randint(1000, 9999)}",
            " TAP",
            f" {rng.randint(1, 28):02d}/0{rng.randint(1, 9)}",
        ]
    )
    return f"{prefix}{body}{store}{place}{tail}".strip()


def make_rows(n: int, table: dict, seed: str, start: date) -> list[dict]:
    rng = random.Random(seed)
    cats = list(table)
    rows = []
    d = start
    for i in range(n):
        cat = rng.choice(cats)
        merchant, lo, hi = rng.choice(table[cat])
        d += timedelta(days=rng.choice([0, 0, 1, 1, 2]))
        amount = -round(rng.uniform(lo, hi), 2)
        rows.append(
            {
                "row_id": i + 1,
                "date": d.isoformat(),
                "description": _descriptor(rng, merchant),
                "amount": f"{amount:.2f}",
                "category": cat,
                "merchant": merchant,
            }
        )
    return rows


def to_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", "description", "amount"])
    for r in rows:
        w.writerow([r["date"], r["description"], r["amount"]])
    return buf.getvalue().encode("utf-8")


PLAN = {  # split -> (merchant table name, files, rows per file)
    "train": ("train", 50, 40),  # 2,000 rows
    "dev": ("train", 5, 40),  # 200 rows
    "test": ("held_out", 5, 20),  # 100 rows
}


def generate(out_root: Path, plan: dict = PLAN, seed: int = SEED) -> dict[str, int]:
    import hashlib

    tables = {"train": TRAIN_MERCHANTS, "held_out": HELD_OUT_MERCHANTS}
    counts = {}
    for split, (table, files, per_file) in plan.items():
        out = out_root / split
        out.mkdir(parents=True, exist_ok=True)
        with (out / "labels.jsonl").open("w", encoding="utf-8") as fh:
            for f in range(files):
                rows = make_rows(
                    per_file,
                    tables[table],
                    f"{seed}-{split}-{f}",
                    date(2025, 1, 1) + timedelta(days=37 * f),
                )
                data = to_csv(rows)
                name = f"tx_{split}_{f:03d}.csv"
                (out / name).write_bytes(data)
                fh.write(
                    json.dumps(
                        {
                            "file": name,
                            "split": split,
                            "merchant_list": table,
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "merchants": sorted({r["merchant"] for r in rows}),
                            "label": {
                                "items": [
                                    {"row_id": r["row_id"], "category": r["category"]} for r in rows
                                ]
                            },
                        }
                    )
                    + "\n"
                )
        counts[split] = files * per_file
    return counts


def main() -> None:
    out = get_settings().data_dir / "synthetic" / "output" / "transactions"
    print("transaction rows written:", generate(out), "->", out)


if __name__ == "__main__":
    sys.exit(main())
