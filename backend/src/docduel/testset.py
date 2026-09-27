"""Lookup of frozen test-set documents (the manifest is created in Phase 2)."""

import json
from functools import lru_cache

from docduel.settings import get_settings


@lru_cache
def _test_hashes() -> frozenset[str]:
    manifest = get_settings().data_dir / "test" / "manifest.json"
    if not manifest.exists():
        return frozenset()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return frozenset(item["sha256"] for item in data.get("documents", []))


def is_test_document(sha256: str) -> bool:
    return sha256 in _test_hashes()


@lru_cache
def _test_docs() -> dict[str, dict]:
    manifest = get_settings().data_dir / "test" / "manifest.json"
    if not manifest.exists():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {item["sha256"]: item for item in data.get("documents", [])}


def frozen_entry(sha256: str) -> dict | None:
    """The frozen test entry (id, task, label) for this file hash, or None."""
    return _test_docs().get(sha256)
