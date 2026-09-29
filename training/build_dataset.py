"""Plan path for tasks 7.1 and 8.5. Run from backend/:

  uv run python ../training/build_dataset.py             # round 1
  uv run python ../training/build_dataset.py --round 2   # round 1 data + verified corrections

Runs the leakage check, then writes data/train/sft_rN_train.jsonl, sft_rN_dev.jsonl and
manifest_rN.json. The code lives in docduel.datasets.sft (importable and tested).
"""

from docduel.datasets.sft import main

if __name__ == "__main__":
    main()
