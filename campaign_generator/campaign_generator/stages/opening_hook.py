from __future__ import annotations

import re
from collections.abc import Callable

from pydantic import BaseModel, Field

from common.llm import LLMClient, LLMError, generate_structured
from common.pack import GenrePack
from ..schemas import LocationCatalog, NPCRoster, OpeningHookDocument, PlotSkeleton, PremiseDocument
from ..seed import CampaignSeed
from ..validation import ValidationLog


PROMPT_FILE = "09_opening_hook.md"

_DANGLING_VERB_PATTERNS = [
    re.compile(r"\bwith\s+a\s+\w+\s+delivers\b", re.IGNORECASE),
    re.compile(r"\bwith\s+a\s+\w+\s+\w+s\b", re.IGNORECASE),
]

_MIN_LENGTH = 80
_MAX_LENGTH = 800


class _OpeningSceneResponse(BaseModel):
    opening_scene: str = Field(min_length=20)


def _collect_proper_nouns(
    premise: PremiseDocument,
    plot: PlotSkeleton,
    npcs: NPCRoster | None,
    locations: LocationCatalog | None,
) -> set[str]:
    nouns: set[str] = set()
    if premise.title:
        nouns.add(premise.title.strip())
    if plot.main_antagonist and plot.main_antagonist.name:
        nouns.add(plot.main_antagonist.name.strip())
    if npcs is not None:
        for npc in npcs.npcs:
            nouns.add(npc.name.strip())
    if locations is not None:
        for location in locations.locations:
            nouns.add(location.name.strip())
    return {noun for noun in nouns if noun and not noun.islower()}


def _detect_issues(text: str, proper_nouns: set[str]) -> list[str]:
    issues: list[str] = []
    if not text or not text.strip():
        issues.append("opening_scene is empty")
        return issues
    if len(text) < _MIN_LENGTH:
        issues.append(f"opening_scene is too short ({len(text)} < {_MIN_LENGTH} chars)")
    if len(text) > _MAX_LENGTH:
        issues.append(f"opening_scene is too long ({len(text)} > {_MAX_LENGTH} chars)")
    for noun in proper_nouns:
        if not noun:
            continue
        if noun in text:
            continue
        if re.search(rf"\b{re.escape(noun)}\b", text, flags=re.IGNORECASE):
            issues.append(f"proper noun {noun!r} appears with wrong casing")
    for pattern in _DANGLING_VERB_PATTERNS:
        match = pattern.search(text)
        if match:
            issues.append(f"ungrammatical fragment {match.group(0)!r}")
    return issues


def _autofix_casing(text: str, proper_nouns: set[str]) -> str:
    fixed = text
    for noun in sorted(proper_nouns, key=len, reverse=True):
        if not noun or noun in fixed:
            continue
        fixed = re.sub(rf"\b{re.escape(noun)}\b", noun, fixed, flags=re.IGNORECASE)
    return fixed


def _deterministic_opening_scene(plot: PlotSkeleton, seed: CampaignSeed) -> str:
    if seed.opening_hook_seed:
        return seed.opening_hook_seed
    act_one = plot.acts[0]
    return (
        f"You arrive at the threshold of {act_one.title}. {plot.hook} "
        "The first scene foregrounds danger, atmosphere, and one human detail worth protecting."
    )


def _character_guidance(seed: CampaignSeed) -> list[str]:
    guidance = [
        "Create someone who belongs in this campaign's pressure points: faith, taint, ruins, or frontier survival.",
        "Give your character one reason to care about the opening hook before the first scene begins.",
        "Choose abilities and gear that let them investigate, survive, or negotiate under pressure.",
    ]
    if seed.protagonist_archetype:
        guidance.insert(0, f"Best fit: {seed.protagonist_archetype}")
    return guidance


def _llm_opening_scene(
    *,
    client: LLMClient,
    system_prompt: str,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    npcs: NPCRoster | None,
    locations: LocationCatalog | None,
    seed: CampaignSeed,
    proper_nouns: set[str],
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> str | None:
    """Try up to 3 times to get an LLM-written opening scene that passes
    post-validation. Returns the cleaned text on success, None on persistent
    failure (caller falls back to deterministic generation)."""
    repair_note = ""
    last_text: str | None = None
    for attempt in range(1, 4):
        context = {
            "premise_title": premise.title,
            "premise_paragraphs": premise.paragraphs,
            "central_conflict": premise.central_conflict,
            "tone_statement": premise.tone_statement,
            "act_one": {
                "title": plot.acts[0].title,
                "goal": plot.acts[0].goal,
            },
            "hook": plot.hook,
            "proper_nouns": sorted(proper_nouns),
            "seed_opening_hook": seed.opening_hook_seed,
            "repair_note": repair_note,
        }
        try:
            response = generate_structured(
                client=client,
                stage_name="opening_hook",
                system_prompt=system_prompt,
                user_prompt=__import__("json").dumps(context, indent=2),
                schema=_OpeningSceneResponse,
                model=model,
                temperature=temperature,
                validation_log=validation_log,
            )
        except LLMError as exc:
            validation_log.write(f"[opening_hook] attempt {attempt} failed: {exc}")
            return None
        last_text = response.opening_scene.strip()
        issues = _detect_issues(last_text, proper_nouns)
        if not issues:
            return last_text
        validation_log.write(
            f"[opening_hook] attempt {attempt} post-validation issues: {'; '.join(issues)}"
        )
        repair_note = (
            "Your previous response had these issues. Fix all of them and try again: "
            + "; ".join(issues)
        )
    if last_text:
        autofixed = _autofix_casing(last_text, proper_nouns)
        remaining = _detect_issues(autofixed, proper_nouns)
        casing_only = all("wrong casing" not in issue for issue in remaining)
        if not remaining or casing_only:
            validation_log.write(
                "[opening_hook] applied deterministic auto-fix for proper-noun casing after 3 LLM attempts"
            )
            return autofixed
        validation_log.write(
            f"[opening_hook] auto-fix could not resolve remaining issues: {'; '.join(remaining)}"
        )
    return None


def render(
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    seed: CampaignSeed,
    *,
    npcs: NPCRoster | None = None,
    locations: LocationCatalog | None = None,
    client: LLMClient | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    validation_log: ValidationLog | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> OpeningHookDocument:
    proper_nouns = _collect_proper_nouns(premise, plot, npcs, locations)

    opening_scene: str | None = None
    if client is not None and system_prompt is not None and validation_log is not None and model is not None and temperature is not None:
        if progress_callback is not None:
            progress_callback("Generating opening hook scene")
        opening_scene = _llm_opening_scene(
            client=client,
            system_prompt=system_prompt,
            premise=premise,
            plot=plot,
            npcs=npcs,
            locations=locations,
            seed=seed,
            proper_nouns=proper_nouns,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )

    if opening_scene is None:
        opening_scene = _deterministic_opening_scene(plot, seed)
        opening_scene = _autofix_casing(opening_scene, proper_nouns)
        if validation_log is not None:
            issues = _detect_issues(opening_scene, proper_nouns)
            if issues:
                validation_log.write(
                    "[opening_hook] deterministic fallback emitted text with residual issues: "
                    + "; ".join(issues)
                )

    return OpeningHookDocument(
        premise=premise.premise_text,
        tone_statement=premise.tone_statement,
        character_creation_guidance=_character_guidance(seed),
        opening_scene=opening_scene,
    )
