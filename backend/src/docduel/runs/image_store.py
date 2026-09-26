"""Short-lived, in-memory copies of prepared images for the describe task.

Rule R7: production keeps no uploaded files. So the resized image lives only in server
memory for 15 minutes after upload, then it is forgotten (also lost on restart).
"""

import time
from collections import OrderedDict

TTL_S = 15 * 60
MAX_ITEMS = 100

_store: OrderedDict[str, tuple[float, bytes]] = OrderedDict()


def put(document_id: str, jpeg: bytes, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    _store[document_id] = (now + TTL_S, jpeg)
    _store.move_to_end(document_id)
    while len(_store) > MAX_ITEMS:
        _store.popitem(last=False)  # drop the oldest


def get(document_id: str, now: float | None = None) -> bytes | None:
    now = time.monotonic() if now is None else now
    item = _store.get(document_id)
    if item is None:
        return None
    expires, jpeg = item
    if now > expires:
        del _store[document_id]
        return None
    return jpeg


def clear() -> None:
    _store.clear()
