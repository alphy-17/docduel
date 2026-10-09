"""Numbers and narration timing for the promo video (rule R5: numbers come from reports/).

  python video/make_data.py      (from the repo root; needs public/vo/*.mp3 + *.json from make_voice.mjs)

Times every narration line from ElevenLabs' character timings, so scenes, sound effects and the
word-by-word captions land exactly on the spoken words.
"""

import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
R = HERE.parent / "reports"


def load(name: str) -> dict:
    return json.loads((R / f"{name}.json").read_text(encoding="utf-8"))


ours = load("eval_small-ft-r1_test-v1_extract_v1")
oa = load("eval_openai_test-v1_extract_v1")
h1, h2 = ours["scores"]["headline"], oa["scores"]["headline"]
hard = {k: load(f"eval_{k}_hard-holdout_extract_v1") for k in ("small-ft-r1", "small-ft-r2")}
t = load("throughput_small-ft-r1")
log = load("training_r1_log")
cost = re.search(r"s of training.*?about US\$([0-9.]+)", (R / "training_r1.md").read_text(encoding="utf-8"))

md = (R / "training_r1.md").read_text(encoding="utf-8")
cord = re.search(r"\| CORD receipts \(extract\) \| (\d+) \|", md)
synth = re.search(r"\| Synthetic invoices[^|]*\| (\d+) \|", md)

data = {
    "cordTrain": int(cord.group(1)),
    "synthTrain": int(synth.group(1)),
    "oursField": h1["field_accuracy"]["value"],
    "openaiField": h2["field_accuracy"]["value"],
    "ratio": h1["field_accuracy"]["value"] / h2["field_accuracy"]["value"],
    "testDocs": ours["docs_scored"],
    "corrections": load("corrections_quality")["documents"],
    "hardPerfectR1": hard["small-ft-r1"]["scores"]["headline"]["perfect_document_rate"]["value"],
    "hardPerfectR2": hard["small-ft-r2"]["scores"]["headline"]["perfect_document_rate"]["value"],
    "hardDateR1": hard["small-ft-r1"]["scores"]["per_field"]["document_date"]["accuracy"],
    "hardDateR2": hard["small-ft-r2"]["scores"]["per_field"]["document_date"]["accuracy"],
    "throughput": [{"c": lv["concurrency"], "usd": lv["cost_per_1000_docs_usd"]} for lv in t["levels"]],
    "openaiUsd": t["openai_cost_per_1000_docs_usd"],
    "trainExamples": log["examples"]["train"],
    "trainMinutes": round(log["train_seconds"] / 60),
    "trainUsd": float(cost.group(1)) if cost else None,
    "gpu": log["gpu"],
    "loss": [round(h["loss"], 5) for h in log["history"] if "loss" in h],
}
(HERE / "src" / "data.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")

# Narration timing. Each clip's leading silence is skipped, so the gap between lines is exactly `pause`.
lines = json.loads((HERE / "script.json").read_text(encoding="utf-8"))["lines"]
said = " ".join(l["caption"] for l in lines)
expect = [f"{data['cordTrain']} real", f"{data['synthTrain']} generated invoices", f"{data['trainMinutes']} minutes",
          f"${data['trainUsd']:.2f}", f"{data['ratio'] * 100:.1f}%", f"{data['corrections']} invoices",
          f"{data['hardPerfectR1']:.0%} to {data['hardPerfectR2']:.0%}"]
missing = [e for e in expect if e not in said]
if missing:
    raise SystemExit(f"script.json disagrees with reports/: {missing}")
if not (data["throughput"][0]["usd"] > data["openaiUsd"] > next(x["usd"] for x in data["throughput"] if x["c"] == 16)):
    raise SystemExit("the cost lines no longer match reports/throughput_small-ft-r1.json")


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)


START = 0.5
cursor, clips = START, []
for line in lines:
    vo = HERE / "public" / "vo"
    al = json.loads((vo / f"{line['id']}.json").read_text(encoding="utf-8"))["alignment"]
    chars, t0s, t1s = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    lead = next(t for c, t in zip(chars, t0s) if c.strip())
    end = max(t for c, t in zip(chars, t1s) if c.strip())
    # When each spoken word starts, as (fraction of the spoken text, seconds after the line starts).
    marks, text = [], "".join(chars)
    for m in re.finditer(r"\S+", text):
        marks.append((m.start() / len(text), t0s[m.start()] - lead))
    # Light caption words at the matching point of the speech (captions may write 800 where the voice says eight hundred).
    cap, words, pos = line["caption"], [], 0
    for w in cap.split(" "):
        f = pos / len(cap)
        t = max(tt for ff, tt in marks if ff <= f + 1e-9)
        words.append({"w": w, "t": round(t, 3)})
        pos += len(w) + 1
    clips.append({"id": line["id"], "caption": cap, "start": round(cursor, 3), "dur": round(end - lead, 3),
                  "offset": round(lead, 3), "file": round(duration(vo / f"{line['id']}.mp3"), 3), "words": words})
    cursor += (end - lead) + line["pause"]

TOTAL = max(60.0, round(cursor + 1.3, 1))
if TOTAL > 66:
    raise SystemExit(f"narration runs to {cursor:.1f} s; shorten script.json or raise the voice speed")
(HERE / "src" / "timeline.json").write_text(json.dumps({"total": TOTAL, "clips": clips}, indent=1) + "\n", encoding="utf-8")
print(f"data.json and timeline.json written; speech ends at {cursor:.1f} s, video is {TOTAL} s")
