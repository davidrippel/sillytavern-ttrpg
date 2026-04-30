from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common.llm import LLMClient, OpenRouterClient, UsageStats
from common.progress import format_duration, format_usage_summary
from common.settings import get_default_model, get_default_temperature, get_dry_run_model
from common.validation import ValidationLog
from pydantic import BaseModel

from .brief import GenreBrief, load_brief
from .schemas import (
    AbilityCatalogDraft,
    AbilityCategoriesDraft,
    AttributesDraft,
    ExampleHooksDraft,
    FailureMovesDraft,
    GeneratorSeedDraft,
    GMOverlay,
    PackDescription,
    ResourcesDraft,
    ReviewChecklistDraft,
    ToneAndPillars,
)
from .stages import (
    ability_catalog as ability_catalog_stage,
)
from .stages import (
    ability_categories as ability_categories_stage,
)
from .stages import (
    attributes as attributes_stage,
)
from .stages import (
    character_template as character_template_stage,
)
from .stages import (
    example_hooks as example_hooks_stage,
)
from .stages import (
    failure_moves as failure_moves_stage,
)
from .stages import (
    generator_seed as generator_seed_stage,
)
from .stages import (
    gm_prompt_overlay as gm_overlay_stage,
)
from .stages import (
    pack_yaml as pack_yaml_stage,
)
from .stages import (
    resources as resources_stage,
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
    "attributes": AttributesDraft,
    "resources": ResourcesDraft,
    "ability_categories": AbilityCategoriesDraft,
    "ability_catalog": AbilityCatalogDraft,
    "gm_prompt_overlay": GMOverlay,
    "failure_moves": FailureMovesDraft,
    "example_hooks": ExampleHooksDraft,
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
    if stage_arg == "all":
        return set(STAGE_MODELS) | {"character_template"}
    selected: set[str] = set()
    valid = set(STAGE_MODELS) | {"character_template"}
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
        # Allow re-running stages against an existing _stages cache, but only
        # if the directory currently contains nothing else (or we're just
        # re-running with cached _stages).
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

    # ----- Stage runners ------------------------------------------------------

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

    # ----- 2. attributes -----
    attributes = _run_or_load(
        "attributes",
        lambda: attributes_stage.run(
            client=client,
            system_prompt=_load_prompt(attributes_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(attributes, AttributesDraft)

    # ----- 3. resources -----
    resources = _run_or_load(
        "resources",
        lambda: resources_stage.run(
            client=client,
            system_prompt=_load_prompt(resources_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            attributes=attributes,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(resources, ResourcesDraft)

    # ----- 4. ability_categories -----
    categories = _run_or_load(
        "ability_categories",
        lambda: ability_categories_stage.run(
            client=client,
            system_prompt=_load_prompt(ability_categories_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            attributes=attributes,
            resources=resources,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(categories, AbilityCategoriesDraft)

    # ----- 5. ability_catalog -----
    catalog = _run_or_load(
        "ability_catalog",
        lambda: ability_catalog_stage.run(
            client=client,
            system_prompt=_load_prompt(ability_catalog_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            attributes=attributes,
            resources=resources,
            categories=categories,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(catalog, AbilityCatalogDraft)

    # ----- 6. character_template (deterministic) -----
    if "character_template" in selected or not _stage_path(stages_dir, "character_template").exists():
        if progress_callback is not None:
            progress_callback("Starting stage: character_template")
        ct_started = time.monotonic()
        ct_usage_started = client.usage_snapshot()
        character_template = character_template_stage.build(attributes, resources)
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

    # ----- 7. gm_prompt_overlay -----
    overlay = _run_or_load(
        "gm_prompt_overlay",
        lambda: gm_overlay_stage.run(
            client=client,
            system_prompt=_load_prompt(gm_overlay_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            attributes=attributes,
            resources=resources,
            categories=categories,
            catalog=catalog,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(overlay, GMOverlay)

    # ----- 8. failure_moves -----
    failure_moves = _run_or_load(
        "failure_moves",
        lambda: failure_moves_stage.run(
            client=client,
            system_prompt=_load_prompt(failure_moves_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            resources=resources,
            categories=categories,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(failure_moves, FailureMovesDraft)

    # ----- 9. example_hooks -----
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

    # ----- 10. generator_seed -----
    generator_seed = _run_or_load(
        "generator_seed",
        lambda: generator_seed_stage.run(
            client=client,
            system_prompt=_load_prompt(generator_seed_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            attributes=attributes,
            resources=resources,
            categories=categories,
            overlay=overlay,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    assert isinstance(generator_seed, GeneratorSeedDraft)

    # ----- 11. pack_yaml (LLM call generates description; rest templated) -----
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

    # ----- 12. review_checklist -----
    retries_log_summary = _summarize_retries_log(retries_log_path)
    checklist = _run_or_load(
        "review_checklist",
        lambda: review_checklist_stage.run(
            client=client,
            system_prompt=_load_prompt(review_checklist_stage.PROMPT_FILE),
            brief=brief,
            tone=tone,
            attributes=attributes,
            resources=resources,
            categories=categories,
            catalog=catalog,
            overlay=overlay,
            failure_moves=failure_moves,
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

    # ----- 13. write + final validation -----
    if progress_callback is not None:
        progress_callback("Writing pack files and running final validation")
    write_pack_files(
        output_dir=output_dir,
        pack_metadata=pack_metadata,
        attributes=attributes,
        resources=resources,
        categories=categories,
        catalog=catalog,
        character_template=character_template,
        overlay=overlay,
        tone=tone,
        inspirations_text=brief.example_inspiration_list,
        failure_moves=failure_moves,
        example_hooks=example_hooks,
        generator_seed=generator_seed,
        checklist=checklist,
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
