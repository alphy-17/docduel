"""Turn Pydantic models into JSON Schemas that OpenAI strict mode accepts (Plan 3.2).

Strict mode rules: every object lists all its properties as required, allows no extra
properties, and optional values are expressed as "type or null" (never by omission).
"""

from typing import Any

from pydantic import BaseModel


def _check(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            props = set(node.get("properties", {}))
            if node.get("additionalProperties") is not False:
                raise ValueError(f"{path}: additionalProperties must be false")
            if set(node.get("required", [])) != props:
                raise ValueError(f"{path}: every property must be required")
        for k, v in node.items():
            _check(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _check(v, f"{path}[{i}]")


def _drop_titles(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _drop_titles(v)
            for k, v in node.items()
            # "title" as a keyword, not as a property called "title"
            if not (k == "title" and isinstance(v, str))
        }
    if isinstance(node, list):
        return [_drop_titles(v) for v in node]
    return node


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for `model`, validated against strict-mode rules."""
    schema = _drop_titles(model.model_json_schema())
    _check(schema)
    return schema


def response_format(model: type[BaseModel]) -> dict[str, Any]:
    """The `response_format` value for Chat Completions (works on OpenAI and vLLM)."""
    return {
        "type": "json_schema",
        "json_schema": {"name": model.__name__, "strict": True, "schema": strict_schema(model)},
    }
