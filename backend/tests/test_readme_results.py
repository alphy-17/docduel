"""The README results block is generated from the committed reports (Plan 9.8, rule R5)."""

import importlib.util

from docduel.settings import BACKEND_DIR


def _module():
    spec = importlib.util.spec_from_file_location(
        "readme_results", BACKEND_DIR / "scripts" / "readme_results.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_block_is_built_from_reports_and_matches_readme() -> None:
    mod = _module()
    block = mod.block()
    assert block.startswith(mod.START) and block.endswith(mod.END)
    assert "None" not in block and "Where our model loses" in block
    # The committed README must hold exactly what the reports say right now.
    assert block in mod.README.read_text(encoding="utf-8")
