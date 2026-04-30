from __future__ import annotations

import json
from typing import Any

from common.llm import LLMClient, generate_structured
from common.validation import ValidationLog
from pydantic import BaseModel


def render_context(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def call_llm(
    *,
    client: LLMClient,
    stage_name: str,
    system_prompt: str,
    context: dict[str, Any],
    schema: type[BaseModel],
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> BaseModel:
    user_prompt = render_context(context)
    return generate_structured(
        client=client,
        stage_name=stage_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=schema,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
