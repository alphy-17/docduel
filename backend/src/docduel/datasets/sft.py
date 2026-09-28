"""Build the fine-tuning set for round 1 (Plan 7.1).

  uv run python -m docduel.datasets.sft            # writes data/train/sft_r1_*.jsonl + manifest

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

ROUND = "r1"
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


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out_dir: Path | None = None) -> dict:
    problems = check_from_disk()
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
    dev = [to_example(r) for r in dev_slice(dev_rows)]
    paths = {
        "train": out_dir / f"sft_{ROUND}_train.jsonl",
        "dev": out_dir / f"sft_{ROUND}_dev.jsonl",
    }
    _write_jsonl(paths["train"], train)
    _write_jsonl(paths["dev"], dev)

    def counts(rows: list[dict]) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in rows:
            c[f"{r['source']}:{r['task']}"] = c.get(f"{r['source']}:{r['task']}", 0) + 1
        return dict(sorted(c.items()))

    manifest = {
        "round": ROUND,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "prompts": ["extract_v1", "categorise_v1"],
        "target": "ground-truth JSON only (CORD vendor/date/number nulls masked from the loss)",
        "leakage_check": "passed",
        "counts": {"train": counts(train), "dev": counts(dev)},
        "files": {k: {"name": p.name, "sha256": _file_hash(p)} for k, p in paths.items()},
        "documents": {
            "train": sorted(r["sha256"] for r in train),
            "dev": sorted(r["sha256"] for r in dev),
        },
    }
    mpath = out_dir / f"manifest_{ROUND}.json"
    mpath.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return {"counts": manifest["counts"], "manifest": str(mpath)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
