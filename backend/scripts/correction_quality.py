"""How accurate were the human corrections? (Phase 8 evidence, rule R5)

  uv run python scripts/correction_quality.py

The hard pool is synthetic, so the generator knows the true answer for every document. This
scores the Owner's corrections and our model's pre-fill against that truth with the normal
scoring rules and writes reports/corrections_quality.json. Run it only after all corrections
are saved: it reads the generator labels, which must not be looked at while correcting.
"""

import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from docduel.datasets.build import _read_jsonl, splits_dir
from docduel.db import Correction, get_engine, init_db
from docduel.routes.corrections import PREFILL_MODEL, prefills
from docduel.scoring.extract import FIELDS, aggregate, score_extraction
from docduel.settings import REPO_DIR


def main() -> None:
    init_db()
    pool = {r["id"]: r for r in _read_jsonl(splits_dir() / "hard_correct.jsonl")}
    pre = prefills()
    with Session(get_engine()) as s:
        rows = list(s.exec(select(Correction)))
    human, model, per_doc = [], [], []
    wrong_fields: dict[str, int] = {}
    for c in sorted(rows, key=lambda c: c.doc_id):
        gold = pool[c.doc_id]["label"]
        h = score_extraction(json.loads(c.payload_json), gold)
        m = score_extraction(pre.get(c.doc_id), gold)
        human.append(h)
        model.append(m)
        for f in FIELDS:
            if f in h.fields and not h.fields[f]["fuzzy"]:
                wrong_fields[f] = wrong_fields.get(f, 0) + 1
        per_doc.append(
            {
                "id": c.doc_id,
                "changed_fields": c.changed_fields,
                "human_fields": f"{h.field_correct}/{h.field_total}",
                "human_perfect": h.perfect,
                "prefill_fields": f"{m.field_correct}/{m.field_total}",
            }
        )
    rnd = lambda d: {k: round(v, 4) for k, v in d.items()}  # noqa: E731
    report = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "documents": len(rows),
        "prefill_model": PREFILL_MODEL,
        "human_corrections_vs_truth": rnd(aggregate(human)),
        "prefill_vs_truth": rnd(aggregate(model)),
        "documents_changed": sum(c.changed_fields > 0 for c in rows),
        "human_wrong_by_field": dict(sorted(wrong_fields.items(), key=lambda kv: -kv[1])),
        "per_doc": per_doc,
    }
    out = REPO_DIR / "reports" / "corrections_quality.json"
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    h, m = report["human_corrections_vs_truth"], report["prefill_vs_truth"]
    print(f"{len(rows)} corrections, {report['documents_changed']} changed from the pre-fill")
    print(f"field accuracy: pre-fill {m['field_accuracy']:.1%} -> human {h['field_accuracy']:.1%}")
    print(f"line-item F1:   pre-fill {m['line_item_f1']:.1%} -> human {h['line_item_f1']:.1%}")
    pm, ph = m["perfect_document_rate"], h["perfect_document_rate"]
    print(f"perfect docs:   pre-fill {pm:.1%} -> human {ph:.1%}")
    print(f"human misses by field: {report['human_wrong_by_field']}")
    print(f"report: reports/{out.name}")


if __name__ == "__main__":
    main()
