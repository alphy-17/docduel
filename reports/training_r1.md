# Fine-tuning round 1: small-ft-r1

Every number here comes from the report files named next to it (rule R5).

## What we trained

- Base model: Qwen/Qwen3.5-4B, revision 851bf6e (the same weights as `small-base`)
- Method: bf16 LoRA with Unsloth 2026.9.11 (transformers 5.5.0, peft 0.21.0, torch 2.12.1)
- LoRA: rank 16, alpha 32, dropout 0. Targets are q/k/v/o and gate/up/down only. The linear-attention (GatedDeltaNet) projections are left alone, so vLLM bug #47639 cannot trigger
- Training: learning rate 2e-4 (linear decay, 10 warm-up steps), 2 epochs, 16 examples per step (4 x 4 accumulation), 170 steps, 8-bit AdamW, seed 2026, max length 4,096 tokens (no example dropped)
- Loss: counted on the answer only. The system text, the few-shot turns and the document are masked. For CORD, the vendor, date and number nulls are masked too, because CORD removed those fields rather than leaving them blank
- Prompt: the exact `extract_v1` and `categorise_v1` prompts used at evaluation, rendered with the model's own chat template with thinking off

## Data (`data/train/manifest_r1.json`)

| Source | Train | Dev slice for validation loss |
|---|---|---|
| CORD receipts (extract) | 800 | 38 |
| Synthetic invoices, templates A-E (extract) | 500 | 37 |
| Synthetic transaction files, 40 rows each (categorise) | 50 | 5 |

- Targets are ground-truth JSON only; no OpenAI output (R3)
- The leakage check passed before the build; no test document or held-out merchant is in train or dev (R4)
- OCR for the 1,045 train pages: Azure Document Intelligence, 348 pages on F0 before the quota ran out, the rest on S0 (about US$0.96)

## Training run (`reports/training_r1_log.json`, `reports/training_r1_loss.png`)

- One Modal L40S, 2,321 s of training (2,439 s including loading), about US$1.32
- Validation loss (dev slice, answer tokens): 0.0347 before, 0.0111 at step 20, 0.0064 at step 80, 0.0059 at the end. Training loss 0.0113 averaged over the run. No sign of the validation loss climbing
- An earlier attempt was cancelled from the client side at step 92 (about US$0.75 lost). The script now saves a checkpoint every 20 steps and resumes from it

## Dev decision rule (Plan 7.6)

| Dev, 150 extract docs + 5 CSV files | small-base | small-ft-r1 |
|---|---|---|
| Field accuracy | 86.4% (83.2-89.3) | **97.9% (96.5-99.1)** |
| Line-item F1 | 82.0% (76.3-86.9) | 92.4% (88.4-95.7) |
| Perfect documents | 43.3% (35.3-51.3) | 82.7% (76.0-88.0) |
| Valid JSON | 100% | 100% |
| Categorise accuracy | 91.5% (89.0-93.5) | 100% |

Field accuracy rose by 11.5 points, above the 5-point bar, so the test set was run once.
Sources: `eval_small-base_dev_*.json`, `eval_small-ft-r1_dev_*.json`.

## Test set v1 (frozen, recorded once)

| Test-v1, 63 extract docs | small-base | small-ft-r1 | OpenAI gpt-6-luna |
|---|---|---|---|
| Field accuracy | 88.7% (84.7-92.1) | **96.3% (94.0-98.5)** | 98.8% (97.4-99.7) |
| Line-item F1 | 70.8% (59.7-81.3) | **90.5% (83.2-96.7)** | 92.8% (85.8-98.1) |
| Perfect documents | 31.7% (20.6-44.4) | **74.6% (63.5-84.2)** | 84.1% (74.6-92.1) |
| Valid JSON | 100% | 100% | 100% |
| Our score as a share of OpenAI's (field accuracy) | 89.8% | **97.5%** | |
| Speed p50 / p95 | 5.5 s / 10.0 s | 6.0 s / 10.9 s | 2.4 s / 4.8 s |
| Cost per 1,000 docs (one at a time / steady load) | $1.34 / $0.35 | $1.41 / $0.36 | $0.20 (warm cache) |

By source (field accuracy, line-item F1, perfect documents):

| Source | small-base | small-ft-r1 |
|---|---|---|
| CORD test receipts (40) | 83.9%, 74.0%, 27.5% | 96.1%, 91.4%, 77.5% |
| Held-out invoice template F (15) | 96.5%, 56.9%, 40.0% | 100%, 86.0%, 86.7% |
| Owner receipts (8) | 86.2%, 100%, 37.5% | 89.7%, 100%, 37.5% |

Per field, small-base to small-ft-r1: payment method 72% to 98%, total 87% to 97%, currency 98% to 100%, tax 89% to 97%, subtotal 88% to 95%, service charge 80% to 100%, date 96% to 100%. Discount fell from 67% to 50% (only 6 documents have one) and document number from 96% to 91% (23 documents).

| Test-v1 categorise, 5 files, held-out merchants | small-base | small-ft-r1 |
|---|---|---|
| Accuracy | 88.0% (81.0-95.0) | **83.0% (70.0-94.0)** |
| Macro F1 | 87.4% (77.6-95.1) | 83.1% (68.6-94.2) |

Sources: `eval_*_test-v1_extract_v1.json`, `eval_*_test-v1_categorise_v1.json`.

## What this means

- Extraction improved a lot and generalised: the biggest gains are on the invoice template the model never saw (line-item F1 +29 points) and on real CORD receipts.
- Categorisation got worse on unseen merchants (dev 100% but test 83%). The model learned the 50 training files' merchant names instead of the rule behind them. 6 of 15 "Other" rows became "Utilities" and 4 "Dining" rows became "Groceries". This is overfitting, and it is round 2's first job.
- The owner receipts barely moved (perfect documents stay at 3 of 8), so real Australian receipts are still the hardest case.
- Speed and cost are almost unchanged: the adapter adds about 0.4 s at p50.

## Ideas for round 2 (Phase 8)

- Categorise: more merchant variety, or fewer categorise examples per epoch, and check against held-out-style merchants on dev
- Discounts and document numbers: more examples with discounts; the owner-receipt corrections loop
- Keep the test set frozen; compare round 2 on dev first, as here
