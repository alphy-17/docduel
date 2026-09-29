"""Build the fine-tuning set for round 1 (Plan 7.1).

  uv run python -m docduel.datasets.sft              # round 1: data/train/sft_r1_*.jsonl + manifest
  uv run python -m docduel.datasets.sft --round 2    # round 2: round 1 + verified corrections x3

Each example is the exact prompt the model sees at evaluation time (system text, few-shot turns,
document) plus the answer we want: the ground-truth JSON only (rule R3: no OpenAI outputs).
The chat template is applied later, on the training GPU, with the base model's own tokenizer.

CORD removed store names and dates, so its labels say null for vendor_name, document_date and
document_number. Training on those nulls would teach the model to leave real vendor names
blank, so for CORD we record where those null values sit in the answer and the trainer skips
them when computing the loss ("mask_spans").
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from docduel.datasets.build import _read_jsonl, _write_jsonl, splits_dir
from docduel.datasets.leakage import check_from_disk
from docduel.runs.prompting import SCHEMAS, build_prompt
from docduel.settings import get_settings

CORRECTION_REPEAT = 3  # Plan 8.5: corrections repeated so 40 documents carry some weight
CORD_UNLABELLED = ("vendor_name", "document_date", "document_number")
DEV_SAMPLE = 80  # validation loss on a fixed slice of dev keeps each check quick


def answer_json(task: str, label: dict) -> str:
    """The target text: the label checked against the task schema, written like the few-shots."""
    model = SCHEMAS[task]
    return json.dumps(model.model_validate(label).model_dump(mode="json"))


def null_spans(answer: str, fields=CORD_UNLABELLED) -> list[list[int]]:
    """Character spans of `null` values for fields the source never labelled."""
    spans = []
    for f in fields:
        key = f'"{f}": null'
        i = answer.find(key)
        if i >= 0:
            start = i + len(key) - len("null")
            spans.append([start, start + len("null")])
    return spans


def to_example(row: dict) -> dict:
    task = row["task"]
    prompt = build_prompt(task, text=row["text"])
    answer = answer_json(task, row["label"])
    return {
        "id": row["id"],
        "task": task,
        "source": row["source"],
        "sha256": row["sha256"],
        "messages": prompt.messages,
        "answer": answer,
        "mask_spans": null_spans(answer) if row["source"] == "cord" else [],
    }


def dev_slice(rows: list[dict], n: int = DEV_SAMPLE) -> list[dict]:
    """A fixed, balanced slice of dev: every source represented, chosen by sorted id."""
    by_source: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda r: r["id"]):
        by_source.setdefault(r["source"], []).append(r)
    out, i = [], 0
    while len(out) < min(n, len(rows)):
        for group in by_source.values():
            if i < len(group) and len(out) < n:
                out.append(group[i])
        i += 1
    return out


def load_corrections() -> list[dict]:
    """Human-verified corrections joined with their OCR text, as training rows (Plan 8.5)."""
    from sqlmodel import Session, select

    from docduel.db import Correction, get_engine, init_db
    from docduel.testset import is_test_document

    init_db()
    pool = {r["id"]: r for r in _read_jsonl(splits_dir() / "hard_correct.jsonl")}
    rows = []
    with Session(get_engine()) as s:
        for c in s.exec(select(Correction).where(Correction.verified_by_human)):
            if c.is_test_document or is_test_document(c.document_sha256):
                sys.exit(f"LEAK: correction {c.doc_id} is a test-set document")
            doc = pool.get(c.doc_id)
            if doc is None or doc["sha256"] != c.document_sha256:
                sys.exit(f"correction {c.doc_id} does not match the hard pool")
            label = json.loads(c.payload_json)
            rows.append(dict(doc, source="correction", task="extract", label=label))
    return sorted(rows, key=lambda r: r["id"])


def mark_used(doc_ids: list[str], round_no: int) -> None:
    from sqlmodel import Session, select

    from docduel.db import Correction, get_engine

    with Session(get_engine()) as s:
        for c in s.exec(select(Correction).where(Correction.doc_id.in_(doc_ids))):
            c.used_in_round = round_no
            s.add(c)
        s.commit()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out_dir: Path | None = None, round_no: int = 1, min_corrections: int = 40) -> dict:
    tag = f"r{round_no}"
    corrections = load_corrections() if round_no >= 2 else []
    if round_no >= 2 and len(corrections) < min_corrections:
        sys.exit(f"only {len(corrections)} verified corrections; need at least {min_corrections}")
    problems = check_from_disk(extra_train=corrections)
    if problems:
        sys.exit("leakage check failed - not building:\n" + "\n".join(problems))
    out_dir = out_dir or get_settings().data_dir / "train"
    train_rows = _read_jsonl(splits_dir() / "train.jsonl")
    dev_rows = _read_jsonl(splits_dir() / "dev.jsonl")
    if not train_rows:
        sys.exit("no data/splits/train.jsonl - run the ocr and splits steps for train first")
    test_hashes = {r["sha256"] for r in _read_jsonl(splits_dir() / "test.jsonl")}
    if any(r["sha256"] in test_hashes for r in train_rows + dev_rows):
        sys.exit("LEAK: a test document is in train or dev")

    train = [to_example(r) for r in train_rows]
    for r in corrections:  # same prompt, the Owner's verified answer as the target
        for k in range(CORRECTION_REPEAT):
            train.append(dict(to_example(r), id=f"{r['id']}#{k + 1}"))
    dev = [to_example(r) for r in dev_slice(dev_rows)]
    paths = {
        "train": out_dir / f"sft_{tag}_train.jsonl",
        "dev": out_dir / f"sft_{tag}_dev.jsonl",
    }
    _write_jsonl(paths["train"], train)
    _write_jsonl(paths["dev"], dev)

    def counts(rows: list[dict]) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in rows:
            c[f"{r['source']}:{r['task']}"] = c.get(f"{r['source']}:{r['task']}", 0) + 1
        return dict(sorted(c.items()))

    manifest = {
        "round": tag,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "prompts": ["extract_v1", "categorise_v1"],
        "target": "ground-truth JSON only (CORD vendor/date/number nulls masked from the loss)"
        + (
            f"; plus {len(corrections)} human-verified corrections x{CORRECTION_REPEAT}"
            if corrections
            else ""
        ),
        "corrections": [{"id": r["id"], "sha256": r["sha256"]} for r in corrections],
        "leakage_check": "passed",
        "counts": {"train": counts(train), "dev": counts(dev)},
        "files": {k: {"name": p.name, "sha256": _file_hash(p)} for k, p in paths.items()},
        "documents": {
            "train": sorted(r["sha256"] for r in train),
            "dev": sorted(r["sha256"] for r in dev),
        },
    }
    mpath = out_dir / f"manifest_{tag}.json"
    mpath.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    if corrections:
        mark_used([r["id"] for r in corrections], round_no)
    return {"counts": manifest["counts"], "manifest": str(mpath)}


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m docduel.datasets.sft")
    ap.add_argument("--round", type=int, default=1, choices=[1, 2])
    a = ap.parse_args(argv)
    print(json.dumps(build(round_no=a.round), indent=2))


if __name__ == "__main__":
    main()
