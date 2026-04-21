from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .artifacts import serialize_clue_graph, serialize_location_catalog, serialize_plot_skeleton
from .llm import LLMClient, OpenRouterClient
from .lorebook import assemble_lorebook
from .pack import GenrePack, load_pack
from .placeholders import infer_protagonist_name_candidates, sanitize_model
from .schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument
from .seed import LoadedSeed, load_seed
from .validation import ValidationLog, validate_cross_stage
from .stages import branches as branches_stage
from .stages import clue_chains as clue_chains_stage
from .stages import factions as factions_stage
from .stages import initial_an as initial_an_stage
from .stages import locations as locations_stage
from .stages import npcs as npcs_stage
from .stages import opening_hook as opening_hook_stage
from .stages import plot_skeleton as plot_stage
from .stages import premise as premise_stage
from .stages import spoilers as spoilers_stage
from .settings import get_default_model, get_default_temperature, get_dry_run_model

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

STAGE_ALIASES = {
    "plot": "plot_skeleton",
    "plot_skeleton": "plot_skeleton",
    "premise": "premise",
    "factions": "factions",
    "npcs": "npcs",
    "locations": "locations",
    "clue_chains": "clue_chains",
    "clues": "clue_chains",
    "branches": "branches",
    "all": "all",
}

STAGE_MODELS: dict[str, type[BaseModel]] = {
    "premise": PremiseDocument,
    "plot_skeleton": PlotSkeleton,
    "factions": FactionSet,
    "npcs": NPCRoster,
    "locations": LocationCatalog,
    "clue_chains": ClueGraph,
    "branches": BranchPlan,
}


class PipelineResult(BaseModel):
    output_dir: Path
    pack: GenrePack
    seed: LoadedSeed


ProgressCallback = Callable[[str], None]


def _load_prompt(filename: str) -> str:
    return (PROMPT_DIR / filename).read_text(encoding="utf-8").strip()


def _load_cached_stage(path: Path, model_cls: type[BaseModel]) -> BaseModel:
    with path.open("r", encoding="utf-8") as handle:
        return model_cls.model_validate(json.load(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _normalize_stage_selection(stage_arg: str) -> set[str]:
    if stage_arg == "all":
        return set(STAGE_MODELS)
    selected = set()
    for raw_name in [token.strip() for token in stage_arg.split(",") if token.strip()]:
        normalized = STAGE_ALIASES.get(raw_name)
        if not normalized:
            raise ValueError(f"unknown stage {raw_name!r}")
        if normalized == "all":
            return set(STAGE_MODELS)
        selected.add(normalized)
    return selected


def _stage_cache_path(stages_dir: Path, stage_name: str) -> Path:
    return stages_dir / f"{stage_name}.json"


def _run_or_load_stage(
    *,
    name: str,
    selected: set[str],
    stages_dir: Path,
    runner,
    model_cls: type[BaseModel],
    progress_callback: ProgressCallback | None = None,
) -> BaseModel:
    cache_path = _stage_cache_path(stages_dir, name)
    if name not in selected and cache_path.exists():
        if progress_callback is not None:
            progress_callback(f"Using cached stage: {name}")
        return _load_cached_stage(cache_path, model_cls)
    if progress_callback is not None:
        progress_callback(f"Starting stage: {name}")
    started_at = time.monotonic()
    result = runner()
    _write_json(cache_path, result.model_dump())
    if progress_callback is not None:
        duration = time.monotonic() - started_at
        progress_callback(f"Completed stage: {name} ({duration:.1f}s)")
    return result


def run_pipeline(
    *,
    genre_path: str | Path,
    seed_path: str | Path,
    output_path: str | Path,
    model: str | None = None,
    dry_run: bool = False,
    random_seed: int | None = None,
    stages: str = "all",
    llm_client: LLMClient | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PipelineResult:
    started_at = time.monotonic()
    output_dir = Path(output_path).resolve()
    stages_dir = output_dir / "stages"
    spoilers_dir = output_dir / "spoilers"
    partials_dir = output_dir / "partials"
    output_dir.mkdir(parents=True, exist_ok=True)
    stages_dir.mkdir(parents=True, exist_ok=True)
    spoilers_dir.mkdir(parents=True, exist_ok=True)
    partials_dir.mkdir(parents=True, exist_ok=True)
    (stages_dir / "calls.jsonl").touch(exist_ok=True)
    (stages_dir / "validation_log.txt").touch(exist_ok=True)

    pack = load_pack(genre_path)
    loaded_seed = load_seed(seed_path, pack)
    if random_seed is not None:
        loaded_seed.resolved.random_seed = random_seed

    validation_log = ValidationLog(stages_dir / "validation_log.txt")
    for warning in loaded_seed.warnings:
        validation_log.write(f"[seed-warning] {warning}")
        if progress_callback is not None:
            progress_callback(f"Seed warning: {warning}")

    selected = _normalize_stage_selection(stages)
    resolved_model = (
        loaded_seed.resolved.model
        or (get_dry_run_model() if dry_run else model)
        or get_default_model()
    )
    temperature = loaded_seed.resolved.temperature or get_default_temperature()
    if progress_callback is not None:
        progress_callback(
            f"Campaign generation started for pack '{pack.metadata.pack_name}' with model '{resolved_model}'"
        )

    client = llm_client or OpenRouterClient(call_log_path=stages_dir / "calls.jsonl")

    premise = _run_or_load_stage(
        name="premise",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=PremiseDocument,
        progress_callback=progress_callback,
        runner=lambda: premise_stage.run(
            client=client,
            system_prompt=_load_prompt(premise_stage.PROMPT_FILE),
            pack=pack,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    premise = sanitize_model(premise)
    _write_json(_stage_cache_path(stages_dir, "premise"), premise.model_dump())

    plot = _run_or_load_stage(
        name="plot_skeleton",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=PlotSkeleton,
        progress_callback=progress_callback,
        runner=lambda: plot_stage.run(
            client=client,
            system_prompt=_load_prompt(plot_stage.PROMPT_FILE),
            pack=pack,
            premise=premise,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    protagonist_names = infer_protagonist_name_candidates(plot.hook, *premise.paragraphs)
    plot = sanitize_model(plot, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "plot_skeleton"), serialize_plot_skeleton(plot))

    opening_hook_draft = opening_hook_stage.render(pack, premise, plot, loaded_seed.resolved)
    _write_text(partials_dir / "opening_hook.partial.txt", opening_hook_draft.render())
    if progress_callback is not None:
        progress_callback("Wrote partials/opening_hook.partial.txt")

    initial_note_draft = initial_an_stage.render(plot)
    _write_text(partials_dir / "initial_authors_note.partial.txt", initial_note_draft.render())
    if progress_callback is not None:
        progress_callback("Wrote partials/initial_authors_note.partial.txt")

    factions = _run_or_load_stage(
        name="factions",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=FactionSet,
        progress_callback=progress_callback,
        runner=lambda: factions_stage.run(
            client=client,
            system_prompt=_load_prompt(factions_stage.PROMPT_FILE),
            pack=pack,
            premise=premise,
            plot=plot,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    factions = sanitize_model(factions, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "factions"), factions.model_dump())

    npcs = _run_or_load_stage(
        name="npcs",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=NPCRoster,
        progress_callback=progress_callback,
        runner=lambda: npcs_stage.run(
            client=client,
            system_prompt=_load_prompt(npcs_stage.PROMPT_FILE),
            pack=pack,
            premise=premise,
            plot=plot,
            factions=factions,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
            progress_callback=progress_callback,
            snapshot_path=partials_dir / "npcs.partial.json",
        ),
    )
    npcs = sanitize_model(npcs, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "npcs"), npcs.model_dump())

    locations = _run_or_load_stage(
        name="locations",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=LocationCatalog,
        progress_callback=progress_callback,
        runner=lambda: locations_stage.run(
            client=client,
            system_prompt=_load_prompt(locations_stage.PROMPT_FILE),
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
            progress_callback=progress_callback,
            snapshot_path=partials_dir / "locations.partial.json",
        ),
    )
    locations = sanitize_model(locations, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "locations"), serialize_location_catalog(locations, plot))

    clue_graph = _run_or_load_stage(
        name="clue_chains",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=ClueGraph,
        progress_callback=progress_callback,
        runner=lambda: clue_chains_stage.run(
            client=client,
            system_prompt=_load_prompt(clue_chains_stage.PROMPT_FILE),
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            locations=locations,
            density=loaded_seed.resolved.clue_chain_density or "medium",
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
            snapshot_path=partials_dir / "clue_chains.partial.json",
            progress_callback=progress_callback,
        ),
    )
    clue_graph = sanitize_model(clue_graph, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "clue_chains"), serialize_clue_graph(clue_graph, plot))

    branches = _run_or_load_stage(
        name="branches",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=BranchPlan,
        progress_callback=progress_callback,
        runner=lambda: branches_stage.run(
            client=client,
            system_prompt=_load_prompt(branches_stage.PROMPT_FILE),
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            locations=locations,
            clue_graph=clue_graph,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    branches = sanitize_model(branches, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "branches"), branches.model_dump())

    cross_stage_errors = validate_cross_stage(pack, plot, factions, npcs, locations, clue_graph, branches)
    if cross_stage_errors:
        for error in cross_stage_errors:
            validation_log.write(f"[cross-stage] {error}")
        raise ValueError("cross-stage validation failed; see stages/validation_log.txt")
    if progress_callback is not None:
        progress_callback("Cross-stage validation passed")

    opening_hook = opening_hook_stage.render(pack, premise, plot, loaded_seed.resolved)
    _write_text(output_dir / "opening_hook.txt", opening_hook.render())
    if progress_callback is not None:
        progress_callback("Wrote opening_hook.txt")

    initial_note = initial_an_stage.render(plot)
    _write_text(output_dir / "initial_authors_note.txt", initial_note.render())
    if progress_callback is not None:
        progress_callback("Wrote initial_authors_note.txt")

    lorebook = assemble_lorebook(
        pack=pack,
        premise=premise,
        plot=plot,
        factions=factions,
        npcs=npcs,
        locations=locations,
        clue_graph=clue_graph,
        branches=branches,
    )
    _write_json(output_dir / "campaign_lorebook.json", lorebook)
    if progress_callback is not None:
        progress_callback("Wrote campaign_lorebook.json")

    spoilers = spoilers_stage.render(
        premise=premise,
        plot=plot,
        factions=factions,
        npcs=npcs,
        locations=locations,
        clues=clue_graph,
        branches=branches,
    )
    _write_text(spoilers_dir / "full_campaign.md", spoilers)
    if progress_callback is not None:
        total_duration = time.monotonic() - started_at
        progress_callback(f"Campaign generation finished ({total_duration:.1f}s)")

    return PipelineResult(output_dir=output_dir, pack=pack, seed=loaded_seed)
