from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

USER_TOKEN = "{{user}}"

_PHRASE_REPLACEMENTS = [
    (re.compile(r"\b[Tt]he protagonist's\b"), "{{user}}'s"),
    (re.compile(r"\b[Tt]he protagonist\b"), USER_TOKEN),
    (re.compile(r"\b[Pp]rotagonist's\b"), "{{user}}'s"),
    (re.compile(r"\b[Pp]rotagonist\b"), USER_TOKEN),
    (re.compile(r"\b[Tt]he player character's\b"), "{{user}}'s"),
    (re.compile(r"\b[Tt]he player character\b"), USER_TOKEN),
    (re.compile(r"\b[Pp]layer character's\b"), "{{user}}'s"),
    (re.compile(r"\b[Pp]layer character\b"), USER_TOKEN),
]


def infer_protagonist_name_candidates(*texts: str) -> set[str]:
    candidates: set[str] = set()
    patterns = [
        re.compile(r"^\s*([A-Z][a-z]+)\b,\s+(?:an|a)\b"),
        re.compile(r"^\s*([A-Z][a-z]+)\b\s+is\b"),
        re.compile(r"^\s*([A-Z][a-z]+)'s\b"),
    ]
    for text in texts:
        if not text:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            for pattern in patterns:
                match = pattern.search(stripped)
                if match:
                    candidates.add(match.group(1))
    return candidates


def sanitize_text(text: str, protagonist_names: set[str] | None = None) -> str:
    updated = text
    for pattern, replacement in _PHRASE_REPLACEMENTS:
        updated = pattern.sub(replacement, updated)

    for name in sorted(protagonist_names or set(), key=len, reverse=True):
        updated = re.sub(rf"\b{re.escape(name)}'s\b", "{{user}}'s", updated)
        updated = re.sub(rf"\b{re.escape(name)}\b", USER_TOKEN, updated)

    return updated


def sanitize_data(value: Any, protagonist_names: set[str] | None = None) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, protagonist_names=protagonist_names)
    if isinstance(value, list):
        return [sanitize_data(item, protagonist_names=protagonist_names) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_data(item, protagonist_names=protagonist_names)
            for key, item in value.items()
        }
    return value


def sanitize_model(model: BaseModel, *, protagonist_names: set[str] | None = None) -> BaseModel:
    payload = sanitize_data(model.model_dump(), protagonist_names=protagonist_names)
    return type(model).model_validate(payload)
