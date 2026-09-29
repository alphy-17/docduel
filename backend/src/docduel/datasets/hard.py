"""Phase 8 hard-case pool (Plan 8.1): 60 template G invoices with heavier scan noise.

66 are generated because Azure OCR finds no text at all on a few of the noisiest scans; the
first 60 readable ones (by id) form the pool, so the choice does not depend on model answers.

  uv run python -m docduel.datasets.invoices --hard                 # write the 60 PDFs + labels
  uv run --group data python -m docduel.datasets.build inventory
  uv run --group data python -m docduel.datasets.build ocr --splits hard
  uv run --group data python -m docduel.datasets.build splits --splits hard
  uv run python -m docduel.datasets.hard                            # 40 to correct, 20 held out

The split is fixed (seed 2026) and written once; running it again refuses to reshuffle.
"""

import json
import random
import sys

from docduel.datasets.build import _read_jsonl, _write_jsonl, splits_dir
from docduel.testset import is_test_document

SEED = 2026
HOLDOUT = 20
POOL = 60


def assign(rows: list[dict], holdout: int = HOLDOUT, seed: int = SEED) -> tuple[list, list]:
    """(to_correct, held_out), chosen by a seeded sample over ids sorted for stability."""
    ordered = sorted(rows, key=lambda r: r["id"])
    held = set(random.Random(seed).sample([r["id"] for r in ordered], holdout))
    return [r for r in ordered if r["id"] not in held], [r for r in ordered if r["id"] in held]


def main() -> None:
    out_correct = splits_dir() / "hard_correct.jsonl"
    out_holdout = splits_dir() / "hard_holdout.jsonl"
    if out_correct.exists() or out_holdout.exists():
        sys.exit("hard pool already split; delete both files only if you really mean to redo it")
    readable = sorted(_read_jsonl(splits_dir() / "hard.jsonl"), key=lambda r: r["id"])
    if len(readable) < POOL:
        sys.exit(f"need {POOL} readable hard documents, found {len(readable)}")
    rows = readable[:POOL]
    if any(is_test_document(r["sha256"]) for r in rows):
        sys.exit("LEAK: a hard-pool document is in the frozen test set")
    correct, holdout = assign(rows)
    _write_jsonl(out_correct, correct)
    _write_jsonl(out_holdout, holdout)
    print(
        json.dumps(
            {"to_correct": len(correct), "held_out": len(holdout), "spare": len(readable) - POOL}
        )
    )


if __name__ == "__main__":
    main()
