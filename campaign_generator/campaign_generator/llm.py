from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from .env import load_project_dotenv
from .retrying import retry_call
from .settings import (
    get_openrouter_api_url,
    get_openrouter_max_retries,
    get_openrouter_timeout_seconds,
    get_stage_max_retries,
)
from .validation import ValidationLog


class LLMError(RuntimeError):
    pass


def _extract_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model did not return valid JSON: {exc}") from exc


class LLMClient:
    def complete(
        self,
        *,
        stage_name: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> str:
        raise NotImplementedError


class OpenRouterClient(LLMClient):
    def __init__(self, *, api_key: str | None = None, call_log_path: Path | None = None) -> None:
        load_project_dotenv()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_url = get_openrouter_api_url()
        self.timeout_seconds = get_openrouter_timeout_seconds()
        self.max_retries = get_openrouter_max_retries()
        self.call_log_path = call_log_path
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is not set. Add it to your shell or campaign_generator/.env.")

    def _call_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _request() -> dict[str, Any]:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        return retry_call(_request, attempts=self.max_retries, base_delay=1.0, exceptions=(httpx.HTTPError,))

    def complete(
        self,
        *,
        stage_name: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> str:
        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = self._call_api(payload)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover - depends on provider error shape.
            raise LLMError(f"unexpected OpenRouter response shape: {response}") from exc

        if self.call_log_path:
            self.call_log_path.parent.mkdir(parents=True, exist_ok=True)
            log_line = {
                "stage": stage_name,
                "model": model,
                "temperature": temperature,
                "request_hash": hashlib.sha256((system_prompt + user_prompt).encode("utf-8")).hexdigest(),
                "response": content,
            }
            with self.call_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(log_line) + "\n")
        return content


class ReplayLLMClient(LLMClient):
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = {key: list(value) if isinstance(value, list) else [value] for key, value in responses.items()}

    @classmethod
    def from_fixture_dir(cls, fixture_dir: str | Path) -> "ReplayLLMClient":
        directory = Path(fixture_dir)
        responses: dict[str, Any] = {}
        for path in sorted(directory.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                responses[path.stem] = json.load(handle)
        return cls(responses)

    def complete(
        self,
        *,
        stage_name: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> str:
        queue = self.responses.get(stage_name)
        if not queue:
            raise LLMError(f"no replay response available for stage {stage_name!r}")
        next_response = queue.pop(0)
        return json.dumps(next_response) if not isinstance(next_response, str) else next_response


def generate_structured(
    *,
    client: LLMClient,
    stage_name: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    attempts: int | None = None,
) -> BaseModel:
    attempts = attempts or get_stage_max_retries()
    schema_blob = json.dumps(schema.model_json_schema(), indent=2, sort_keys=True)
    repair_note = ""

    for attempt in range(1, attempts + 1):
        prompt = (
            f"{user_prompt}\n\n"
            "Return JSON only.\n"
            f"Required schema:\n{schema_blob}\n"
            f"{repair_note}"
        )
        raw = client.complete(
            stage_name=stage_name,
            system_prompt=system_prompt,
            user_prompt=prompt,
            model=model,
            temperature=temperature,
        )
        try:
            payload = _extract_json(raw)
            return schema.model_validate(payload)
        except (ValidationError, LLMError) as exc:
            validation_log.write(f"[{stage_name}] attempt {attempt} failed: {exc}")
            repair_note = f"Previous response failed validation. Repair these issues and try again:\n{exc}\n"

    raise LLMError(f"{stage_name} failed after {attempts} attempts")
