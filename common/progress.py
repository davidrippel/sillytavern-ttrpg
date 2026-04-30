from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .llm import LLMClient, UsageStats

ProgressCallback = Callable[[str], None]


def format_duration(duration_seconds: float) -> str:
    if duration_seconds >= 60:
        return f"{duration_seconds / 60:.1f}m"
    return f"{duration_seconds:.1f}s"


def format_usage_summary(usage: UsageStats) -> str:
    call_label = "call" if usage.calls == 1 else "calls"
    return f"{usage.calls} {call_label}, {usage.total_tokens} tokens, {usage.cost:.4f} credits"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def load_cached_stage(path: Path, model_cls: type[BaseModel]) -> BaseModel:
    with path.open("r", encoding="utf-8") as handle:
        return model_cls.model_validate(json.load(handle))


def stage_cache_path(stages_dir: Path, stage_name: str) -> Path:
    return stages_dir / f"{stage_name}.json"


def run_or_load_stage(
    *,
    name: str,
    selected: set[str],
    stages_dir: Path,
    runner: Callable[[], BaseModel],
    model_cls: type[BaseModel],
    client: LLMClient,
    progress_callback: ProgressCallback | None = None,
) -> BaseModel:
    cache_path = stage_cache_path(stages_dir, name)
    if name not in selected and cache_path.exists():
        if progress_callback is not None:
            progress_callback(f"Using cached stage: {name}")
        return load_cached_stage(cache_path, model_cls)
    if progress_callback is not None:
        progress_callback(f"Starting stage: {name}")
    started_at = time.monotonic()
    usage_started_at = client.usage_snapshot()
    result = runner()
    write_json(cache_path, result.model_dump())
    if progress_callback is not None:
        duration = time.monotonic() - started_at
        stage_usage = client.usage_snapshot() - usage_started_at
        progress_callback(
            f"Completed stage: {name} ({format_duration(duration)}, {format_usage_summary(stage_usage)})"
        )
    return result


def run_stage_with_timing(
    *,
    name: str,
    runner: Callable[[], Any],
    client: LLMClient,
    progress_callback: ProgressCallback | None = None,
) -> Any:
    """Time and report a stage that doesn't fit the cached BaseModel pattern.

    Used by stages whose output is not a single pydantic model (e.g. plain
    file writes, deterministic templates).
    """
    if progress_callback is not None:
        progress_callback(f"Starting stage: {name}")
    started_at = time.monotonic()
    usage_started_at = client.usage_snapshot()
    result = runner()
    if progress_callback is not None:
        duration = time.monotonic() - started_at
        stage_usage = client.usage_snapshot() - usage_started_at
        progress_callback(
            f"Completed stage: {name} ({format_duration(duration)}, {format_usage_summary(stage_usage)})"
        )
    return result
