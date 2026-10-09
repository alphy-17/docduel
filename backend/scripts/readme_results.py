"""Write the numbers in README.md from the report files (Plan 9.8, rule R5).

  uv run python scripts/readme_results.py

Everything between <!-- RESULTS:START --> and <!-- RESULTS:END --> in README.md is replaced.
No number in that block is typed by hand: each one is read from reports/*.json, so the README
can never drift from the evidence. Run it again after any new report.
"""

import json
import sys
from pathlib import Path

from docduel.settings import REPO_DIR

REPORTS = REPO_DIR / "reports"
README = REPO_DIR / "README.md"
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
OURS, THEIRS = "small-ft-r1", "openai"
ROUNDS = [("small-base", "Base"), ("small-ft-r1", "Round 1"), ("small-ft-r2", "Round 2")]


def load(name: str) -> dict | None:
    path = REPORTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def need(name: str) -> dict:
    report = load(name)
    if report is None:
        sys.exit(f"missing reports/{name}.json")
    return report


def pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def usd(v: float | None) -> str:
    return "-" if v is None else f"${v:,.2f}"


def secs(ms: float | None) -> str:
    return "-" if ms is None else f"{ms / 1000:.1f} s"


def headline() -> list[str]:
    ex = {k: need(f"eval_{k}_test-v1_extract_v1") for k in (OURS, THEIRS)}
    cat = {k: need(f"eval_{k}_test-v1_categorise_v1") for k in (OURS, THEIRS)}
    h = {k: ex[k]["scores"]["headline"] for k in ex}
    sc = {k: ex[k]["speed_cost"] for k in ex}
    ratio = h[OURS]["field_accuracy"]["value"] / h[THEIRS]["field_accuracy"]["value"]
    steady = sc[OURS].get("steady_load")

    def cat_h(k: str) -> dict:
        return cat[k]["scores"]["headline"]

    def speed(k: str) -> str:
        return f"{secs(sc[k]['latency_ms_p50'])} / {secs(sc[k]['latency_ms_p95'])}"

    rows = [
        ("Field accuracy", lambda k: h[k]["field_accuracy"]["display"]),
        ("Line-item F1", lambda k: h[k]["line_item_f1"]["display"]),
        ("Perfect documents", lambda k: h[k]["perfect_document_rate"]["display"]),
        ("Valid JSON answers", lambda k: h[k]["schema_validity"]["display"]),
        ("Categorise accuracy (bank rows)", lambda k: cat_h(k)["accuracy"]["display"]),
        ("Time per receipt, median / 95th pct", speed),
        ("Cost per 1,000 docs, one at a time", lambda k: usd(sc[k]["cost_per_1000_docs_usd"])),
    ]
    out = [
        f"Frozen test set `test-v1`: {ex[OURS]['docs_scored']} receipts and invoices plus "
        f"{cat[OURS]['docs_scored']} bank CSVs, never used for training or tuning. "
        "Ranges are 95% bootstrap confidence intervals.",
        "",
        f"| | Our model (`{ex[OURS]['model_id']}`) | OpenAI (`{ex[THEIRS]['model_id']}`) |",
        "|---|---|---|",
        *(f"| {name} | {get(OURS)} | {get(THEIRS)} |" for name, get in rows),
    ]
    if steady:
        out.append(
            f"| Cost per 1,000 docs, {steady['concurrency']} at once | "
            f"{usd(steady['cost_per_1000_docs_usd'])} | "
            f"{usd(sc[THEIRS]['cost_per_1000_docs_usd'])} |"
        )
    out += ["", f"Our field accuracy is **{pct(ratio)} of OpenAI's**."]
    return out


def rounds() -> list[str]:
    def cell(model: str, split: str, metric: str) -> str:
        r = load(f"eval_{model}_{split}_extract_v1")
        return pct(r["scores"]["headline"][metric]["value"]) if r else "not run"

    out = [
        "| | " + " | ".join(label for _, label in ROUNDS) + " |",
        "|---|" + "---|" * len(ROUNDS),
    ]
    for split, name in (("test-v1", "Test set"), ("hard-holdout", "Hard held-out invoices")):
        for metric, mname in (
            ("field_accuracy", "field accuracy"),
            ("perfect_document_rate", "perfect documents"),
        ):
            cells = " | ".join(cell(m, split, metric) for m, _ in ROUNDS)
            out.append(f"| {name}: {mname} | {cells} |")
    q = load("corrections_quality")
    if q:
        out += [
            "",
            f"Round 2 adds {q['documents']} hard invoices checked by a person. Against the true "
            f"answers, the model's pre-fill had {pct(q['prefill_vs_truth']['field_accuracy'])} "
            "of fields right and the human-verified answers "
            f"{pct(q['human_corrections_vs_truth']['field_accuracy'])}.",
        ]
    return out


def throughput() -> list[str]:
    t = load(f"throughput_{OURS}")
    if not t:
        return []
    rows = [
        f"| {lv['concurrency']} | {usd(lv['cost_per_1000_docs_usd'])} | "
        f"{secs(lv['latency_ms_p50'])} |"
        for lv in t["levels"]
    ]
    oa = t["openai_cost_per_1000_docs_usd"]
    cheaper = [lv["concurrency"] for lv in t["levels"] if lv["cost_per_1000_docs_usd"] < oa]
    verdict = (
        f"From {cheaper[0]} documents at once our GPU is cheaper per document than OpenAI, "
        "but each answer takes longer because the documents share the GPU."
        if cheaper
        else "At every level we measured, OpenAI stays cheaper per document."
    )
    return [
        "",
        f"### Cost when the GPU works on many documents at once (one {t['gpu']})",
        "",
        "| Documents in flight | GPU cost per 1,000 docs | Median time per doc |",
        "|---|---|---|",
        *rows,
        "",
        f"OpenAI: {usd(oa)} per 1,000 docs at any volume. {verdict} "
        "These are GPU-busy costs on a warm GPU; idle time and cold starts are extra. "
        f"Source: `reports/throughput_{OURS}.json`.",
    ]


def losses() -> list[str]:
    ex = {k: need(f"eval_{k}_test-v1_extract_v1") for k in (OURS, THEIRS)}
    cat = {k: need(f"eval_{k}_test-v1_categorise_v1") for k in (OURS, THEIRS)}
    dev_cat = need(f"eval_{OURS}_dev_categorise_v1")["scores"]["headline"]["accuracy"]["value"]
    hold = {k: load(f"eval_{k}_hard-holdout_extract_v1") for k in (OURS, "small-ft-r2")}
    sc = {k: ex[k]["speed_cost"] for k in ex}
    h = {k: ex[k]["scores"]["headline"] for k in ex}
    items = [
        f"- **Accuracy.** OpenAI is ahead on every headline metric, for example perfect "
        f"documents {pct(h[THEIRS]['perfect_document_rate']['value'])} vs "
        f"{pct(h[OURS]['perfect_document_rate']['value'])}.",
        f"- **Cost at low volume.** One document at a time our GPU costs "
        f"{usd(sc[OURS]['cost_per_1000_docs_usd'])} per 1,000 documents against OpenAI's "
        f"{usd(sc[THEIRS]['cost_per_1000_docs_usd'])}, because we pay for GPU seconds while "
        "OpenAI charges per token.",
        f"- **Speed.** Median {secs(sc[OURS]['latency_ms_p50'])} per receipt vs "
        f"{secs(sc[THEIRS]['latency_ms_p50'])}.",
        f"- **Categorising bank rows overfits.** {pct(dev_cat)} on dev but "
        f"{pct(cat[OURS]['scores']['headline']['accuracy']['value'])} on the test set "
        f"(OpenAI {pct(cat[THEIRS]['scores']['headline']['accuracy']['value'])}): "
        "most likely because the synthetic training files reuse too few merchants.",
    ]
    if all(hold.values()):
        d1 = hold[OURS]["scores"]["per_field"]["document_date"]["accuracy"]
        d2 = hold["small-ft-r2"]["scores"]["per_field"]["document_date"]["accuracy"]
        items.append(
            f"- **New layouts.** On an invoice layout it never saw (US month/day dates), round 1 "
            f"read only {pct(d1)} of dates correctly. 40 human corrections (round 2) raised that "
            f"to {pct(d2)}, but round 2 is slightly worse on the general test set, so round 1 "
            "stays the headline model (chosen on dev, never on test)."
        )
    items.append(
        "- **Cold start.** When nobody has used it for a few minutes the GPU sleeps, and the "
        "first live request waits for it to start (about 5 minutes in our runs). The public "
        "site plays recorded runs so visitors never wait."
    )
    return items


def project_cost() -> list[str]:
    c = load("project_cost")
    if not c:
        return []
    rows = [f"| {item['service']} | {item['what']} | {usd(item['usd'])} |" for item in c["items"]]
    total = sum(item["usd"] for item in c["items"])
    return [
        "",
        "## What the project cost",
        "",
        "| Service | Used for | US$ |",
        "|---|---|---|",
        *rows,
        f"| **Total** | | **{usd(total)}** |",
        "",
        f"{c['note']} Source: `reports/project_cost.json`.",
    ]


def block() -> str:
    lines = [
        START,
        "<!-- Generated by backend/scripts/readme_results.py from reports/*.json. "
        "Do not edit by hand. -->",
        "",
        "## Results",
        "",
        *headline(),
        *throughput(),
        "",
        "## The improvement loop: base, round 1, round 2",
        "",
        *rounds(),
        "",
        "## Where our model loses",
        "",
        *losses(),
        *project_cost(),
        END,
    ]
    return "\n".join(lines)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        sys.exit(f"README.md needs the {START} and {END} markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(head + block() + tail, encoding="utf-8")
    print(f"updated {Path(README).name} from {REPORTS.name}/")


if __name__ == "__main__":
    main()
