"""Plan path for the leakage check (rule R4). Run from the repo root:

  uv run --project backend python training/leakage_check.py

Exits non-zero if any test document or held-out merchant appears in train/dev data.
"""

import sys

from docduel.datasets.leakage import main

if __name__ == "__main__":
    sys.exit(main())
