# DocDuel architecture

How the pieces fit together, and why they were built this way. Scores are not repeated here; they live in the README and `reports/`.

## The three parts

```
                    ┌──────────────────────────────────────────────┐
 visitor ──────────▶│ Frontend: React 19 + Vite + Tailwind (Vercel) │
                    │  replay mode: public/demo/*.json (no backend) │
                    │  live mode: X-Access-Code header              │
                    └───────────────┬──────────────────────────────┘
                                    │ HTTPS + server-sent events
                    ┌───────────────▼──────────────────────────────┐
                    │ Backend: FastAPI in Docker                    │
                    │ (Azure Container Apps, 0 to 1 replica)        │
                    │  ingest → run → stream → score                │
                    └──────┬──────────────┬───────────────┬────────┘
                           │              │               │
              Azure Document     OpenAI gpt-6-luna   Modal: vLLM 0.30 on one L4
              Intelligence (OCR) (Structured Outputs) Qwen3.5-4B + LoRA adapters
                                                     (scales to zero)
```

## A live run, step by step

1. **Upload** (`POST /api/documents`, `routes/documents.py`). The file type is checked from its bytes, not its name. Limits: 10 MB, 3 pages, 200 CSV rows (`ingest/limits.py`).
2. **Read the text** (`ingest/`). A PDF with a text layer is read directly with pypdfium2. Scans and photos go to Azure Document Intelligence (`prebuilt-read`); results are cached by file hash so the same page is never paid for twice. CSVs become a numbered table of rows.
3. **Start the run** (`POST /api/runs`). The task is checked against the document (Extract needs a receipt or invoice, Categorise needs a bank CSV).
4. **Stream** (`GET /api/runs/{id}/stream`, `runs/orchestrator.py`). Both models get the identical prompt (`runs/prompting.py`, templates in `backend/prompts/`) at the same moment. Every chunk is pushed to the browser as a server-sent event: `run.started`, `model.delta`, `model.completed` (answer, validity, time, tokens, cost), `model.error`, and finally `run.completed`.
5. **Score** (`scoring/`). If the file's hash is in the frozen test manifest, a `score.completed` event compares each field with the answer key. Otherwise the page only shows where the two models agree.

## Why the public site uses replays

The small model runs on a GPU that sleeps when idle; waking it takes minutes, and every run costs money. So the public site plays **recordings of real runs** (`backend/scripts/record_replays.py`). The recorder uploads each sample to a local backend, runs both live models and saves every streamed event with its timestamp. In the browser, `playReplay` in `frontend/src/lib/api.ts` feeds those events through the same handlers as a live stream, with the original timing. The Benchmark page reads `public/demo/benchmark.json`, exported from the same API by `backend/scripts/export_static.py`.

## Live mode safeguards

- **Access code** on every paid action, checked in `guard.py`.
- **Rate limit:** 30 uploads plus runs per visitor per hour, in memory.
- **No stored uploads** in production (`KEEP_UPLOADS=false`). Images used by the Describe task stay in memory only.
- **The Corrections page and API are switched off** in production (`CORRECTIONS_ENABLED=false`).
- **GPU warm-up** (`warmup.py`, `GET /api/gpu`). Azure ends any request after 240 seconds, but a cold GPU takes longer than that to start. So the site asks the backend to wake the GPU first, waits until it answers, and only then starts the run. It stops asking once the GPU is ready, so an open tab never keeps the GPU running.
- **Secrets** are Azure Container Apps secrets, injected as environment variables; none are in the image or the repo.

## Models and serving

- `config/models.yaml` is the only place model IDs live. `duel.left` is the headline model: the training round with the best **dev** score.
- The small model is served by vLLM on Modal (`training/modal_serve.py`) behind Modal's proxy auth, with the LoRA adapters (`small-ft-r1`, `small-ft-r2`) loaded next to the base weights, so one GPU serves every round.
- Cost: OpenAI is billed per token (`config/pricing.yaml`). Our model is billed per GPU second, so its cost per document depends on how many documents share the GPU at once. The Duel shows the one-at-a-time cost; `backend/scripts/throughput.py` measures it with several in flight.

## Data, training and evaluation

```
CORD receipts ─┐
synthetic      ├─▶ build splits ─▶ leakage check ─▶ train / dev / test-v1 (frozen, hashed)
invoices + CSV ┘        (datasets/build.py, leakage.py)
                                         │
             train ─▶ SFT examples (datasets/sft.py) ─▶ LoRA on Modal (training/modal_train.py)
                                         │
             dev ─▶ choose the round ─▶ test-v1 scored once ─▶ reports/*.json ─▶ README, Benchmark
```

- **Labels are ground truth only.** No answer from OpenAI (or any other model) is used as a training target.
- **Loss on the answer only.** The prompt and document tokens are masked. For CORD, fields the dataset removed are masked too, so the model is not taught to answer "null" for them.
- **Round 2 corrections** come from the Corrections page: the round 1 model pre-fills each hard invoice, a person checks it against the page image, and only verified answers are saved. A correction can never be a test document; it is checked by hash.
- **Evaluation** (`python -m docduel.eval`) runs a model over a split, saves every answer, and writes `reports/eval_<model>_<split>_<prompt>.json` plus a Markdown summary. Confidence intervals come from bootstrap resampling over documents. `--rescore` re-scores saved answers for free.

## Hosting

| Part | Where | Cost model |
|---|---|---|
| Frontend | Vercel (static build of `frontend/`) | free tier |
| Backend | Azure Container Apps, Consumption plan, 0.5 vCPU, 1 GiB, min 0 / max 1 replica | free monthly allowance; nothing when scaled to zero |
| Backend image | GitHub Container Registry, built by CI after the tests pass | free for a public image |
| GPU | Modal, one L4, scales to zero after 5 idle minutes | per second while running |
| OCR | Azure Document Intelligence S0 | per page |

The SQLite database lives in `/tmp` inside the container and disappears when the app scales to zero. Nothing on the public site depends on it: replays and the Benchmark are static files.
