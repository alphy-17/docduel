"""Leakage check (Plan rule R4): no test document may appear in training or dev data.

Compares file SHA-256 across splits, and merchant names across transaction splits.
Exits non-zero on any overlap.  uv run --group data python -m docduel.datasets.leakage
"""

import json
import sys
from pathlib import Path

from docduel.settings import get_settings


def find_leaks(train_like: list[dict], test: list[dict]) -> list[str]:
    problems = []
    test_hashes = {r["sha256"]: r["id"] for r in test}
    for r in train_like:
        if r["sha256"] in test_hashes:
            problems.append(
                f"file hash overlap: {r['id']} ({r['split']}) == {test_hashes[r['sha256']]} (test)"
            )
    test_merchants: dict[str, str] = {}
    for r in test:
        for m in r.get("merchants", []):
            test_merchants[m.upper()] = r["id"]
    for r in train_like:
        for m in r.get("merchants", []):
            if m.upper() in test_merchants:
                problems.append(
                    f"merchant overlap: '{m}' in {r['id']} ({r['split']}) and "
                    f"{test_merchants[m.upper()]} (test)"
                )
    return problems


def _load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def check_from_disk(extra_train: list[dict] | None = None) -> list[str]:
    inv = get_settings().data_dir / "splits" / "inventory.jsonl"
    if not inv.exists():
        return ["no inventory found - run python -m docduel.datasets.build inventory"]
    rows = _load(inv)
    test = [r for r in rows if r["split"] == "test"]
    manifest = get_settings().data_dir / "test" / "manifest.json"
    if manifest.exists():  # once frozen, the manifest is the source of truth for the test set
        test = json.loads(manifest.read_text(encoding="utf-8"))["documents"]
    # "hard" = Phase 8 pool: its corrections become training data, so it is checked too
    train_like = [r for r in rows if r["split"] in ("train", "dev", "hard")] + (extra_train or [])
    return find_leaks(train_like, test)


def main() -> int:
    problems = check_from_disk()
    if problems:
        print(f"LEAKAGE CHECK FAILED: {len(problems)} problem(s)")
        for p in problems[:50]:
            print(" -", p)
        return 1
    print("leakage check passed: no test document or held-out merchant in train/dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
