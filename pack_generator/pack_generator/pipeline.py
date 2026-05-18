from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common.llm import LLMClient, OpenRouterClient
from common.progress import format_duration, format_usage_summary
from common.settings import get_default_model, get_default_temperature, get_dry_run_model
from common.validation import ValidationLog
from pydantic import BaseModel

from .brief import GenreBrief, load_brief
from .schemas import (
    AdvantagesDisadvantagesDraft,
    ComplicationsDraft,
    ExampleHooksDraft,
    GeneratorSeedDraft,
    GMOverlay,
    NamingDraft,
    PackDescription,
    ReviewChecklistDraft,
    ToneAndPillars,
)
from .stages import (
    advantages_disadvantages as advantages_disadvantages_stage,
)
from .stages import (
    character_template as character_template_stage,
)
from .stages import (
    complications as complications_stage,
)
from .stages import (
    example_hooks as example_hooks_stage,
)
from .stages import (
    generator_seed as generator_seed_stage,
)
from .stages import (
    gm_prompt_overlay as gm_overlay_stage,
)
from .stages import (
    naming as naming_stage,
)
from .stages import (
    pack_yaml as pack_yaml_stage,
)
from .stages import (
    review_checklist as review_checklist_stage,
)
from .stages import (
    tone_and_pillars as tone_stage,
)
from .writer import validate_written_pack, write_pack_files

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

ProgressCallback = Callable[[str], None]


# Stages that produce a pydantic-modelled draft we cache to disk.
STAGE_MODELS: dict[str, type[BaseModel]] = {
    "tone_and_pillars": ToneAndPillars,
    "gm_prompt_overlay": GMOverlay,
    "advantages_disadvantages": AdvantagesDisadvantagesDraft,
    "complications": ComplicationsDraft,
    "example_hooks": ExampleHooksDraft,
    "naming": NamingDraft,
    "generator_seed": GeneratorSeedDraft,
    "pack_yaml": PackDescription,
    "review_checklist": ReviewChecklistDraft,
}

LLM_STAGES = list(STAGE_MODELS.keys())


class PipelineResult(BaseModel):
    output_dir: Path
    pack_name: str


def _load_prompt(filename: str) -> str:
    return (PROMPT_DIR / filename).read_text(encoding="utf-8").strip()


def _normalize_stage_selection(stage_arg: str) -> set[str]:
    valid = set(STAGE_MODELS) | {"character_template"}
    if stage_arg == "all":
        return set(valid)
    selected: set[str] = set()
    for raw in [token.strip() for token in stage_arg.split(",") if token.strip()]:
        if raw == "all":
            return valid
        if raw not in valid:
            raise ValueError(f"unknown stage {raw!r}; valid stages: {sorted(valid)}")
        selected.add(raw)
    return selected


def _stage_path(stages_dir: Path, name: str) -> Path:
    return stages_dir / f"{name}.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _load_cached(path: Path, model_cls: type[BaseModel]) -> BaseModel:
    with path.open("r", encoding="utf-8") as handle:
        return model_cls.model_validate(json.load(handle))


def run_pipeline(
    *,
    brief_path: str | Path,
    output_path: str | Path,
    model: str | None = None,
    dry_run: bool = False,
    stages: str = "all",
    llm_client: LLMClient | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PipelineResult:
    brief = load_brief(brief_path)

    output_dir = Path(output_path).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        non_stage_children = [p for p in output_dir.iterdir() if p.name != "_stages"]
        if non_stage_children:
            raise ValueError(
                f"output directory {output_dir} is not empty; refusing to overwrite. "
                f"Found: {[p.name for p in non_stage_children]}"
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    stages_dir = output_dir / "_stages"
    stages_dir.mkdir(parents=True, exist_ok=True)
    calls_log = stages_dir / "calls.jsonl"
    calls_log.touch(exist_ok=True)
    validation_log = ValidationLog(stages_dir / "validation_log.txt")
    retries_log_path = stages_dir / "retries_log.txt"
    retries_log_path.touch(exist_ok=True)

    selected = _normalize_stage_selection(stages)
    resolved_model = model or (get_dry_run_model() if dry_run else get_default_model())
    temperature = get_default_temperature()
    client = llm_client or OpenRouterClient(call_log_path=calls_log)

    if progress_callback is not None:
        progress_callback(
            f"Pack generation started for brief {brief.pack_name!r} with model {resolved_model!r}"
        )

    overall_started = time.monotonic()

    def _run_or_load(name: str, runner: Callable[[], BaseModel]) -> BaseModel:
        cache_path = _stage_path(stages_dir, name)
        if name not in selected and cache_path.exists():
            if progress_callback is not None:
                progress_callback(f"Using cached stage: {name}")
            return _load_cached(cache_path, STAGE_MODELS[name])
        return _run_with_timing(name, runner, cache_path)

    def _run_with_timing(name: str, runner: Callable[[], BaseModel], cache_path: Path) -> BaseModel:
        if progress_callback is not None:
            progress_callback(f"Starting stage: {name}")
        stage_started = time.monotonic()
        usage_started = client.usage_snapshot()
        attempts_before = _validation_attempt_count(validation_log.path, name)
        result = runner()
        _write_json(cache_path, result.model_dump())
        if progress_callback is not None:
            duration = time.monotonic() - stage_started
            stage_usage = client.usage_snapshot() - usage_started
            progress_callback(
                f"Completed stage: {name} ({format_duration(duration)}, {format_usage_summary(stage_usage)})"
            )
        attempts_after = _validation_attempt_count(validation_log.path, name)
        retries_observed = max(0, attempts_after - attempts_before)
        if retries_observed:
            with retries_log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{name}: {retries_observed} retries\n")
        return result

    # ----- 1. tone_and_pillars -----
    tone = _run_or_load(
        "tone_and_pillars",
        lambda: tone_stage.run(
            client=client,
            system_prompt=_load_prompt(tone_stage.PROMPT_FILE),
            brief=brief,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(tone, ToneAndPillars)

    # ----- 2. gm_prompt_overlay -----
    overlay = _run_or_load(
        "gm_prompt_overlay",
        lambda: gm_overlay_stage.run(
            client=client,
            system_prompt=_load_prompt(gm_overlay_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(overlay, GMOverlay)

    # ----- 3. advantages_disadvantages -----
    advantages_disadvantages = _run_or_load(
        "advantages_disadvantages",
        lambda: advantages_disadvantages_stage.run(
            client=client,
            system_prompt=_load_prompt(advantages_disadvantages_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(advantages_disadvantages, AdvantagesDisadvantagesDraft)

    # ----- 4. complications -----
    complications = _run_or_load(
        "complications",
        lambda: complications_stage.run(
            client=client,
            system_prompt=_load_prompt(complications_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(complications, ComplicationsDraft)

    # ----- 5. character_template (deterministic) -----
    if "character_template" in selected or not _stage_path(stages_dir, "character_template").exists():
        if progress_callback is not None:
            progress_callback("Starting stage: character_template")
        ct_started = time.monotonic()
        ct_usage_started = client.usage_snapshot()
        character_template = character_template_stage.build()
        _write_json(_stage_path(stages_dir, "character_template"), character_template)
        if progress_callback is not None:
            duration = time.monotonic() - ct_started
            stage_usage = client.usage_snapshot() - ct_usage_started
            progress_callback(
                f"Completed stage: character_template ({format_duration(duration)}, {format_usage_summary(stage_usage)})"
            )
    else:
        if progress_callback is not None:
            progress_callback("Using cached stage: character_template")
        with _stage_path(stages_dir, "character_template").open("r", encoding="utf-8") as handle:
            character_template = json.load(handle)

    # ----- 6. example_hooks -----
    example_hooks = _run_or_load(
        "example_hooks",
        lambda: example_hooks_stage.run(
            client=client,
            system_prompt=_load_prompt(example_hooks_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(example_hooks, ExampleHooksDraft)

    # ----- 7. naming -----
    naming = _run_or_load(
        "naming",
        lambda: naming_stage.run(
            client=client,
            system_prompt=_load_prompt(naming_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(naming, NamingDraft)

    # ----- 8. generator_seed -----
    generator_seed = _run_or_load(
        "generator_seed",
        lambda: generator_seed_stage.run(
            client=client,
            system_prompt=_load_prompt(generator_seed_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(generator_seed, GeneratorSeedDraft)

    # ----- 9. pack_yaml (LLM generates the description; rest is templated) -----
    pack_description = _run_or_load(
        "pack_yaml",
        lambda: pack_yaml_stage.run(
            client=client,
            system_prompt=_load_prompt(pack_yaml_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(pack_description, PackDescription)
    pack_metadata = pack_yaml_stage.build_metadata(brief, pack_description)

    # ----- 10. review_checklist -----
    retries_log_summary = _summarize_retries_log(retries_log_path)
    checklist = _run_or_load(
        "review_checklist",
        lambda: review_checklist_stage.run(
            client=client,
            system_prompt=_load_prompt(review_checklist_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            overlay=overlay,
            complications=complications,
            advantages_disadvantages=advantages_disadvantages,
            example_hooks=example_hooks,
            generator_seed=generator_seed,
            pack_description=pack_description,
            retries_log=retries_log_summary,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(checklist, ReviewChecklistDraft)

    # ----- 11. write + final validation -----
    if progress_callback is not None:
        progress_callback("Writing pack files and running final validation")
    write_pack_files(
        output_dir=output_dir,
        pack_metadata=pack_metadata,
        character_template=character_template,
        overlay=overlay,
        tone=tone,
        inspirations_text=brief.example_inspiration_list,
        complications=complications,
        advantages_disadvantages=advantages_disadvantages,
        example_hooks=example_hooks,
        generator_seed=generator_seed,
        checklist=checklist,
        naming=naming,
    )
    try:
        validate_written_pack(output_dir)
    except Exception as exc:
        validation_log.write(f"[final-validation] {exc}")
        raise

    if progress_callback is not None:
        total = time.monotonic() - overall_started
        usage = client.usage_snapshot()
        progress_callback(
            f"Pack generation finished ({format_duration(total)}, {format_usage_summary(usage)}, model={resolved_model})"
        )

    return PipelineResult(output_dir=output_dir, pack_name=brief.pack_name)


def _validation_attempt_count(log_path: Path, stage_name: str) -> int:
    if not log_path.exists():
        return 0
    needle = f"[{stage_name}] attempt"
    count = 0
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if needle in line:
                count += 1
    return count


def _summarize_retries_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    summary: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            stage, _, count = line.partition(":")
            try:
                n = int(count.strip().split()[0])
            except (ValueError, IndexError):
                continue
            summary.append({"stage": stage.strip(), "retries": n})
    return summary
