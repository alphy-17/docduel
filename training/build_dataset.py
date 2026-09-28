"""Plan path for task 7.1. Run from backend/:

  uv run python ../training/build_dataset.py

Runs the leakage check, then writes data/train/sft_r1_train.jsonl, sft_r1_dev.jsonl and
manifest_r1.json. The code lives in docduel.datasets.sft (importable and tested).
"""

import json

from docduel.datasets.sft import build

if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
