"""Record real Duel runs for the public replay mode (Plan 9.2, decision D18).

  uv run python scripts/record_replays.py            # needs the local backend on :8000

Each replay is a real run of both live models, saved with the timing of every streamed event,
so the public site can play it back without waking the GPU or spending money. Nothing is
invented: the files hold exactly what the backend sent. Cost: one run per entry below.

Writes frontend/public/demo/replays/<id>.json and index.json. Re-running overwrites them.
"""

import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv

from docduel.datasets.build import _read_jsonl, data_dir, splits_dir
from docduel.models.registry import duel_keys, load_models
from docduel.settings import BACKEND_DIR, REPO_DIR

API = "http://127.0.0.1:8000/api"
SAMPLES = REPO_DIR / "frontend" / "public" / "samples"
OUT = REPO_DIR / "frontend" / "public" / "demo" / "replays"
HARD_SAMPLE = "dense-invoice.pdf"

# (id, sample file, task, title). Four extract, one categorise, one summarise.
PLAN = [
    ("cafe-receipt-extract", "cafe-receipt.png", "extract", "Café receipt"),
    ("scanned-receipt-extract", "scanned-receipt.pdf", "extract", "Scanned receipt"),
    ("tax-invoice-extract", "tax-invoice.pdf", "extract", "Tax invoice"),
    ("dense-invoice-extract", HARD_SAMPLE, "extract", "Dense invoice (hard layout)"),
    ("bank-transactions-categorise", "bank-transactions.csv", "categorise", "Bank transactions"),
    ("tax-invoice-summarise", "tax-invoice.pdf", "summarise", "Tax invoice"),
]


def copy_hard_sample() -> None:
    """A held-out template G invoice (never trained on) becomes the fifth sample file."""
    if (SAMPLES / HARD_SAMPLE).exists():
        return
    row = next(r for r in _read_jsonl(splits_dir() / "hard_holdout.jsonl"))
    src = data_dir() / row["path"]
    if src.suffix.lower() != ".pdf":
        sys.exit(f"expected a PDF for the hard sample, got {src.name}")
    shutil.copyfile(src, SAMPLES / HARD_SAMPLE)
    print(f"copied held-out invoice {row['id']} -> samples/{HARD_SAMPLE}")


def warm_gpu() -> None:
    """Wake the Modal server first so the recording shows warm speed, not a cold start."""
    base, token = os.environ["MODAL_VLLM_BASE_URL"], os.environ["MODAL_VLLM_API_KEY"]
    auth = {"Authorization": f"Bearer {token}"}
    t = time.monotonic()
    # While the container boots, Modal can answer 503; keep asking for up to 6 minutes.
    while True:
        try:
            r = httpx.get(f"{base}/models", headers=auth, timeout=120)
            if r.status_code == 200:
                break
            status = r.status_code
        except httpx.TransportError as e:
            status = type(e).__name__
        waited = time.monotonic() - t
        if waited > 360:
            sys.exit(f"GPU server still not ready after {waited:.0f} s (last answer: {status})")
        print(f"  waking the GPU... ({status}, {waited:.0f} s)")
        time.sleep(10)
    print(f"GPU awake after {time.monotonic() - t:.0f} s")


def record(c: httpx.Client, rid: str, sample: str, task: str, title: str) -> dict:
    path = SAMPLES / sample
    doc = c.post(f"{API}/documents", files={"file": (sample, path.read_bytes())}).json()
    if "document_id" not in doc:
        sys.exit(f"upload failed for {sample}: {doc}")
    run = c.post(f"{API}/runs", json={"document_id": doc["document_id"], "task": task}).json()
    events, name = [], None
    t0 = time.monotonic()
    with c.stream("GET", f"{API}/runs/{run['run_id']}/stream", timeout=300) as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:") and name:
                ms = round((time.monotonic() - t0) * 1000)
                events.append({"t": ms, "event": name, "data": json.loads(line[5:])})
                name = None
    kinds = [e["event"] for e in events]
    if "run.completed" not in kinds or "model.error" in kinds:
        sys.exit(f"{rid}: the run did not finish cleanly ({kinds[-3:]}); nothing saved")
    return {
        "id": rid,
        "title": title,
        "sample": sample,
        "task": task,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "document": doc,
        "events": events,
    }


def main() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    copy_hard_sample()
    warm_gpu()
    OUT.mkdir(parents=True, exist_ok=True)
    models = load_models()
    left, right = duel_keys()
    index = {
        "models": {k: {"model_id": models[k].model_id} for k in (left, right)},
        "replays": [],
    }
    with httpx.Client(timeout=120) as c:
        for rid, sample, task, title in PLAN:
            rep = record(c, rid, sample, task, title)
            (OUT / f"{rid}.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
            done = [e for e in rep["events"] if e["event"] == "model.completed"]
            secs = ", ".join(f"{e['data']['model_key']} {e['t'] / 1000:.1f}s" for e in done)
            print(f"{rid}: {len(rep['events'])} events ({secs})")
            index["replays"].append({k: rep[k] for k in ("id", "title", "sample", "task")})
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(PLAN)} replays to frontend/public/demo/replays/")


if __name__ == "__main__":
    main()
