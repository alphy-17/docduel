"""Build the exact messages both models receive (Plan 3.1). Same prompt for both = fair duel.

Templates live in backend/prompts/<task>_v1.md; few-shot examples (train split only) in
backend/prompts/fewshot/. Few-shot examples are sent as earlier user/assistant turns, which
shows the model the exact input -> output pattern we expect.
"""

import base64
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel

from docduel.schemas.extraction import ReceiptExtraction, SummaryOutput, TransactionCategories
from docduel.schemas.strict import response_format
from docduel.settings import BACKEND_DIR

Task = Literal["extract", "categorise", "summarise", "custom", "describe"]
PROMPTS_DIR = BACKEND_DIR / "prompts"
VERSION = "v1"

SCHEMAS: dict[str, type[BaseModel] | None] = {
    "extract": ReceiptExtraction,
    "categorise": TransactionCategories,
    "summarise": SummaryOutput,
    "custom": None,  # plain text, unscored
    "describe": None,  # plain text, unscored
}
FEWSHOT_TASKS = {"extract", "categorise"}


@dataclass
class Prompt:
    task: str
    version: str  # e.g. "extract_v1"
    messages: list[dict[str, Any]]
    response_format: dict[str, Any] | None


@lru_cache
def _system(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


@lru_cache
def _fewshot(name: str) -> tuple[dict, ...]:
    path = PROMPTS_DIR / "fewshot" / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source_split") != "train":
        raise ValueError(f"{path.name}: few-shot examples must come from the train split")
    return tuple(data["examples"])


def _doc_message(text: str) -> str:
    return f"Document:\n<document>\n{text}\n</document>"


def build_prompt(
    task: Task,
    text: str | None = None,
    instructions: str | None = None,
    image: tuple[bytes, str] | None = None,  # (bytes, mime type) for describe
) -> Prompt:
    if task not in SCHEMAS:
        raise ValueError(f"unknown task: {task}")
    name = f"{task}_{VERSION}"
    messages: list[dict[str, Any]] = [{"role": "system", "content": _system(name)}]

    if task in FEWSHOT_TASKS:
        for ex in _fewshot(name):
            messages.append({"role": "user", "content": _doc_message(ex["text"])})
            messages.append({"role": "assistant", "content": json.dumps(ex["output"])})

    if task == "describe":
        if image is None:
            raise ValueError("describe needs an image")
        data, mime = image
        url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        content: Any = [
            {"type": "text", "text": "Describe this image."},
            {"type": "image_url", "image_url": {"url": url}},
        ]
    else:
        if text is None:
            raise ValueError(f"{task} needs document text")
        content = _doc_message(text)
        if task == "custom":
            if not instructions or not instructions.strip():
                raise ValueError("custom needs instructions")
            content += f"\n\nInstruction: {instructions.strip()}"
    messages.append({"role": "user", "content": content})

    model = SCHEMAS[task]
    return Prompt(task, name, messages, response_format(model) if model else None)
