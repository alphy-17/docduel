# Fine-tuning round 2: small-ft-r2 (human corrections)

Every number here comes from the report files named next to it (rule R5).

## What changed from round 1

Only the data. Round 2 trains from the base model again (not on top of round 1) with exactly the round 1 settings: bf16 LoRA r16/alpha 32 on attention + MLP, learning rate 2e-4, 2 epochs, batch 16, seed 2026, loss on the answer only. Source: `reports/training_r2_log.json`.

| Training data | Round 1 | Round 2 |
|---|---|---|
| CORD receipts | 800 | 800 |
| Synthetic invoices A-E | 500 | 500 |
| Transaction files | 50 | 50 |
| Human-verified corrections (hard invoices, template G), each x3 | 0 | 40 (120 examples) |

## The corrections (`reports/corrections_quality.json`)

- Pool: 60 new-layout invoices (template G: dense, small text, US month/day dates, no printed currency, about half heavy scans). 66 were generated because Azure OCR found no text at all on 5 of the noisiest scans; the first 60 readable ones were used. Fixed split: 40 to correct, 20 held out.
- The Owner checked each document against the page image in the Corrections page, which was pre-filled by small-ft-r1 (never OpenAI, rule R3). 32 of 40 were changed.
- Because the invoices are synthetic, both can be scored against the true answers:

| Against the true answers (40 docs) | small-ft-r1 pre-fill | Owner's verified answers |
|---|---|---|
| Field accuracy | 64.3% | 98.7% |
| Line-item F1 | 56.4% | 99.3% |
| Perfect documents | 20.0% | 90.0% |

The Owner missed 4 fields in total (one each of date, number, currency, payment).

## Training run

1,470 examples, 184 steps, 2,443 s on one L40S (about US$1.35), dev loss 0.0349 to 0.0076 (round 1 reached 0.0059), nothing dropped for length.

## Results

### Hard held-out invoices (20 template G documents, never trained on)

| | small-base | small-ft-r1 | small-ft-r2 |
|---|---|---|---|
| Field accuracy | 68.6% (53.0-81.6) | 74.5% (60.9-85.2) | **85.6% (71.8-96.7)** |
| Line-item F1 | 75.0% (53.2-93.2) | 75.3% (54.5-91.9) | 73.9% (53.4-91.7) |
| Perfect documents | 15.0% | 10.0% | **70.0% (50.0-90.0)** |
| Date | 15% | 20% | **90%** |
| Currency | 80% | 85% | **100%** |

The corrections taught two rules that generalise to unseen documents of this layout: dates here are month/day, and the currency follows the address and tax. Line items and totals did not move: on the heavy scans the OCR text itself is damaged, so there is nothing for a correction to teach.

### Dev (150 extract docs, 5 CSV files)

| | small-ft-r1 | small-ft-r2 |
|---|---|---|
| Field accuracy | 97.9% (96.5-99.1) | 97.0% (94.8-98.5) |
| Line-item F1 | 92.4% | 90.4% |
| Perfect documents | 82.7% | 80.7% |
| Categorise accuracy | 100% | 100% |

### Frozen test set v1 (recorded once)

| | small-ft-r1 | small-ft-r2 | OpenAI |
|---|---|---|---|
| Field accuracy | 96.3% (94.0-98.5) | 95.1% (92.1-97.6) | 98.8% |
| Line-item F1 | 90.5% (83.2-96.7) | 85.5% (78.1-93.0) | 92.8% |
| Perfect documents | 74.6% (63.5-84.2) | 65.1% (54.0-76.2) | 84.1% |
| Categorise accuracy | 83.0% | 82.0% (71.0-94.0) | 100% |

By source (field accuracy, line-item F1, perfect documents), r1 to r2: CORD receipts 96.1/91.4/77.5 to 93.5/86.2/67.5; invoice template F 100/86.0/86.7 to 100/82.0/73.3; Owner receipts 89.7/100/37.5 to 89.7/93.3/37.5.

## What this means (honest reading)

- **Corrections work where they are aimed.** On the new layout, 40 checked documents raised perfect documents from 2 of 20 to 14 of 20, mostly by fixing a systematic date-format mistake.
- **They cost a little elsewhere.** On the general test set r2 is slightly worse than r1, most visibly on CORD line items and perfect documents. The field-accuracy intervals overlap, so the drop may be noise, but the direction matches dev. The likely cause: 120 repeated examples of one unusual layout (US dates, dense text) pulled the model towards that layout. Repeating 40 documents three times is a lot of weight for so few.
- **Which model is "ours".** The Benchmark picks our headline model by dev field accuracy (never by the test set): small-ft-r1 (97.9%) over small-ft-r2 (97.0%). small-ft-r2 stays available in the Duel for invoices like template G.
- Categorise overfitting from round 1 is unchanged (the clean-experiment decision kept categorise data the same).

## What we would try next

- Weight the corrections less (x1 or x2) or mix in more varied hard documents, then compare on dev and the hard holdout together.
- Improve the scan OCR (or send the page image as well as the text) for the fields corrections cannot fix: line items and totals on heavy scans.
- Categorise: more merchant variety (separate from the corrections experiment).
