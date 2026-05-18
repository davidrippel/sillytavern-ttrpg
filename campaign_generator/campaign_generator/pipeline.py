"""Campaign generator pipeline (v2 — story-mode only).

Stages, in order:

1. premise           — central conflict, tone, thematic pillars.
2. plot_skeleton     — acts (title + goal), antagonist, hook,
                       thematic spine. No beats.
3. factions          — 2-4 factions with goals/methods/tensions.
4. npcs              — full roster, story-mode advantage phrases,
                       optional discovery surfaces.
5. locations         — sensory-rich locations with discovery surfaces.
6. truths            — the campaign's atomic truth set (the answer key
                       the GM never sees as a whole).
7. complications     — campaign-specific narrative complications.
8. branches          — 4-10 if/then contingencies referencing NPCs,
                       locations, factions, and truth ids.
9. sample_characters — story-mode sample protagonists.
10. opening_hook     — player-facing premise + opening scene.
11. lorebook         — assembled JSON (v2 constant entries).

The retired v1 stages (nodes, clue_chains, pc_known_npcs, spoilers,
node_generation, graph, initial_an) are gone with the v3 extension's
move away from beats and node graphs. The extension assembles the
runtime AN itself; we only ship an empty starter file.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from common.llm import LLMClient, OpenRouterClient, UsageStats
from common.pack import GenrePack, load_pack
from common.settings import get_default_model, get_default_temperature, get_dry_run_model

from .artifacts import serialize_location_catalog, serialize_plot_skeleton
from .diversity import collect_recent_names, pick_diversity_seed
from .lorebook import assemble_lorebook
from .placeholders import infer_protagonist_name_candidates, sanitize_model
from .schemas import (
    BranchPlan,
    ComplicationSet,
    FactionSet,
    LocationCatalog,
    NPCRoster,
    PlotSkeleton,
    PremiseDocument,
    SampleCharacterSet,
    TruthSet,
)
from .seed import LoadedSeed, load_seed
from .stages import branches as branches_stage
from .stages import complications as complications_stage
from .stages import factions as factions_stage
from .stages import locations as locations_stage
from .stages import npcs as npcs_stage
from .stages import opening_hook as opening_hook_stage
from .stages import plot_skeleton as plot_stage
from .stages import premise as premise_stage
from .stages import sample_characters as sample_characters_stage
from .stages import truths as truths_stage
from .validation import ValidationLog, validate_cross_stage

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

STAGE_ALIASES = {
    "premise": "premise",
    "plot": "plot_skeleton",
    "plot_skeleton": "plot_skeleton",
    "factions": "factions",
    "npcs": "npcs",
    "locations": "locations",
    "truths": "truths",
    "complications": "complications",
    "branches": "branches",
    "samples": "sample_characters",
    "sample_characters": "sample_characters",
    "all": "all",
}

STAGE_MODELS: dict[str, type[BaseModel]] = {
    "premise": PremiseDocument,
    "plot_skeleton": PlotSkeleton,
    "factions": FactionSet,
    "npcs": NPCRoster,
    "locations": LocationCatalog,
    "truths": TruthSet,
    "complications": ComplicationSet,
    "branches": BranchPlan,
    "sample_characters": SampleCharacterSet,
}


class PipelineResult(BaseModel):
    output_dir: Path
    pack: GenrePack
    seed: LoadedSeed

    model_config = {"arbitrary_types_allowed": True}


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


def _slugify_title(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title.strip()).strip("_").lower()
    return slug or "campaign_lorebook"


def _format_duration(seconds: float) -> str:
    return f"{seconds / 60:.1f}m" if seconds >= 60 else f"{seconds:.1f}s"


def _format_usage_summary(usage: UsageStats) -> str:
    call_label = "call" if usage.calls == 1 else "calls"
    return f"{usage.calls} {call_label}, {usage.total_tokens} tokens, {usage.cost:.4f} credits"


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


def _run_or_load(
    *,
    name: str,
    selected: set[str],
    stages_dir: Path,
    model_cls: type[BaseModel],
    client: LLMClient,
    runner: Callable[[], BaseModel],
    progress_callback: ProgressCallback | None,
    resume: bool,
) -> BaseModel:
    cache_path = _stage_cache_path(stages_dir, name)
    if (name not in selected or resume) and cache_path.exists():
        if progress_callback is not None:
            progress_callback(f"Using cached stage: {name}")
        return _load_cached_stage(cache_path, model_cls)
    if progress_callback is not None:
        progress_callback(f"Starting stage: {name}")
    started_at = time.monotonic()
    usage_started = client.usage_snapshot()
    result = runner()
    _write_json(cache_path, result.model_dump())
    if progress_callback is not None:
        duration = time.monotonic() - started_at
        usage = client.usage_snapshot() - usage_started
        progress_callback(
            f"Completed stage: {name} ({_format_duration(duration)}, {_format_usage_summary(usage)})"
        )
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
    resume: bool = False,
) -> PipelineResult:
    started_at = time.monotonic()
    output_dir = Path(output_path).resolve()
    stages_dir = output_dir / "stages"
    partials_dir = output_dir / "partials"
    output_dir.mkdir(parents=True, exist_ok=True)
    stages_dir.mkdir(parents=True, exist_ok=True)
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

    # ---- 1. premise -----------------------------------------------------
    premise: PremiseDocument = _run_or_load(
        name="premise",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=PremiseDocument,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: premise_stage.run(
            client=client,
            system_prompt=_load_prompt("01_premise.md"),
            pack=pack,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    premise = sanitize_model(premise)
    _write_json(_stage_cache_path(stages_dir, "premise"), premise.model_dump())

    # ---- 2. plot_skeleton ----------------------------------------------
    plot: PlotSkeleton = _run_or_load(
        name="plot_skeleton",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=PlotSkeleton,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: plot_stage.run(
            client=client,
            system_prompt=_load_prompt("02_plot_skeleton.md"),
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

    # ---- 3. factions ----------------------------------------------------
    factions: FactionSet = _run_or_load(
        name="factions",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=FactionSet,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: factions_stage.run(
            client=client,
            system_prompt=_load_prompt("03_factions.md"),
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

    # ---- 4. npcs --------------------------------------------------------
    recent_npc_names, recent_location_names = collect_recent_names(
        campaigns_dir=output_dir.parent,
        current_dir=output_dir,
    )
    diversity_seed = pick_diversity_seed(loaded_seed.resolved.random_seed, pack=pack)
    if progress_callback is not None:
        progress_callback(
            f"Diversity seed: register={diversity_seed['cultural_register']}; "
            f"district={diversity_seed['district_flavor']}; "
            f"avoiding {len(recent_npc_names)} recent NPC names and "
            f"{len(recent_location_names)} recent location names"
        )

    npcs: NPCRoster = _run_or_load(
        name="npcs",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=NPCRoster,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: npcs_stage.run(
            client=client,
            system_prompt=_load_prompt("04_npc.md"),
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
            avoid_names=recent_npc_names,
            diversity_seed=diversity_seed,
        ),
    )
    npcs = sanitize_model(npcs, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "npcs"), npcs.model_dump())

    # ---- 5. locations ---------------------------------------------------
    locations: LocationCatalog = _run_or_load(
        name="locations",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=LocationCatalog,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: locations_stage.run(
            client=client,
            system_prompt=_load_prompt("05_location.md"),
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
            avoid_names=recent_location_names,
            diversity_seed=diversity_seed,
        ),
    )
    locations = sanitize_model(locations, protagonist_names=protagonist_names)
    _write_json(
        _stage_cache_path(stages_dir, "locations"),
        serialize_location_catalog(locations),
    )

    # ---- 6. truths ------------------------------------------------------
    truths: TruthSet = _run_or_load(
        name="truths",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=TruthSet,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: truths_stage.run(
            client=client,
            system_prompt=_load_prompt("06_truths.md"),
            pack=pack,
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            locations=locations,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    truths = sanitize_model(truths, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "truths"), truths.model_dump())

    # ---- 7. complications ----------------------------------------------
    complications: ComplicationSet = _run_or_load(
        name="complications",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=ComplicationSet,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: complications_stage.run(
            client=client,
            system_prompt=_load_prompt("07_complications.md"),
            pack=pack,
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            truths=truths,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    complications = sanitize_model(complications, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "complications"), complications.model_dump())

    # ---- 8. branches ----------------------------------------------------
    branches: BranchPlan = _run_or_load(
        name="branches",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=BranchPlan,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: branches_stage.run(
            client=client,
            system_prompt=_load_prompt("08_branches.md"),
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            locations=locations,
            truths=truths,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    branches = sanitize_model(branches, protagonist_names=protagonist_names)
    _write_json(_stage_cache_path(stages_dir, "branches"), branches.model_dump())

    # ---- 9. sample characters ------------------------------------------
    sample_characters: SampleCharacterSet = _run_or_load(
        name="sample_characters",
        selected=selected,
        stages_dir=stages_dir,
        model_cls=SampleCharacterSet,
        client=client,
        progress_callback=progress_callback,
        resume=resume,
        runner=lambda: sample_characters_stage.run(
            client=client,
            system_prompt=_load_prompt(sample_characters_stage.PROMPT_FILE),
            pack=pack,
            premise=premise,
            plot=plot,
            factions=factions,
            npcs=npcs,
            locations=locations,
            seed=loaded_seed.resolved,
            model=resolved_model,
            temperature=temperature,
            validation_log=validation_log,
        ),
    )
    sample_characters = sanitize_model(sample_characters, protagonist_names=protagonist_names)
    _write_json(
        _stage_cache_path(stages_dir, "sample_characters"),
        sample_characters.model_dump(),
    )

    # ---- Cross-stage sanity -------------------------------------------
    validate_cross_stage(
        plot=plot,
        factions=factions,
        npcs=npcs,
        locations=locations,
        truths=truths,
        validation_log=validation_log,
    )
    if progress_callback is not None:
        progress_callback("Cross-stage validation passed")

    # ---- 10. opening hook ---------------------------------------------
    opening_hook = opening_hook_stage.render(
        pack,
        premise,
        plot,
        loaded_seed.resolved,
        npcs=npcs,
        locations=locations,
        client=client,
        system_prompt=_load_prompt(opening_hook_stage.PROMPT_FILE),
        prior_knowledge_system_prompt=_load_prompt(opening_hook_stage.PRIOR_KNOWLEDGE_PROMPT_FILE),
        model=resolved_model,
        temperature=temperature,
        validation_log=validation_log,
        progress_callback=progress_callback,
    )
    _write_text(output_dir / "opening_hook.txt", opening_hook.render())
    if progress_callback is not None:
        progress_callback("Wrote opening_hook.txt")

    # ---- 11. starter Author's Note ------------------------------------
    # In v3 the extension assembles the AN deterministically from state on
    # every turn. The campaign generator only ships a small starter file
    # that holds the scene context for turn 0; everything else fills in
    # as play begins.
    initial_an = _starter_authors_note(premise, plot)
    _write_text(output_dir / "initial_authors_note.txt", initial_an)
    if progress_callback is not None:
        progress_callback("Wrote initial_authors_note.txt")

    # ---- 12. lorebook --------------------------------------------------
    lorebook = assemble_lorebook(
        pack=pack,
        premise=premise,
        plot=plot,
        factions=factions,
        npcs=npcs,
        locations=locations,
        truths=truths,
        complications=complications,
        branches=branches,
        sample_characters=sample_characters,
    )
    lorebook_filename = _slugify_title(premise.title) + ".json"
    _write_json(output_dir / lorebook_filename, lorebook)
    if progress_callback is not None:
        progress_callback(f"Wrote {lorebook_filename}")

    if progress_callback is not None:
        total_duration = time.monotonic() - started_at
        progress_callback(
            f"Campaign generation finished ({_format_duration(total_duration)}, "
            f"{_format_usage_summary(client.usage_snapshot())})"
        )

    return PipelineResult(output_dir=output_dir, pack=pack, seed=loaded_seed)


def _starter_authors_note(premise: PremiseDocument, plot: PlotSkeleton) -> str:
    """A minimal turn-0 Author's Note.

    The v3 extension regenerates the AN from state on every turn, so
    this file is overwritten almost immediately. We still produce a
    plausible starting state for the GM in case the player sends a
    message before the first extraction has run.
    """
    spine = " | ".join(plot.thematic_spine[:3])
    return "\n".join([
        f"Thematic spine: {spine}",
        "Live threads: (none yet — the campaign is about to begin)",
        "Recent facts: (none yet)",
        f"Scene context: Where: {plot.acts[0].title}. Tension: {plot.acts[0].goal}.",
        "On-screen NPCs: (set as the opening scene plays out)",
        "Tone reminders: See __pack_gm_overlay for the genre voice and posture.",
        "",
        (
            "Response length cap: Cap your reply at the base prompt's length rules: "
            "1–2 short paragraphs by default (~80–120 words), 3 paragraphs only for scene "
            "transitions or climaxes. Never four."
        ),
    ])
