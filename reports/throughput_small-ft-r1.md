# Throughput: small-ft-r1 on one L4

Created 2026-10-09T00:55:59+00:00. Train-split extract documents, speed only.

| In flight | Documents | Batch time (s) | Median time per doc (ms) | GPU cost per 1,000 docs |
|---|---|---|---|---|
| 1 | 8 | 47.1 | 5408 | $1.308 |
| 8 | 32 | 30.1 | 5773 | $0.208 |
| 16 | 64 | 48.2 | 8527 | $0.167 |
| 32 | 128 | 68.3 | 13338 | $0.118 |

OpenAI (gpt-6-luna) on the test set: $0.197 per 1,000 docs.
