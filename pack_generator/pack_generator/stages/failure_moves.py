from __future__ import annotations

import re

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import (
    AbilityCategoriesDraft,
    FailureMovesDraft,
    GMOverlay,
    ResourcesDraft,
    ToneAndPillars,
)
from ._common import call_llm

PROMPT_FILE = "07_failure_moves.md"


UNIVERSAL_MOVES = [
    "Reveal an unwelcome truth or danger the player didn't know.",
    "Separate the protagonist from something they value.",
    "Force a hard choice between two things they want to keep.",
    "Burn a resource — gear breaks, torch dies, spell cost, ammunition spent.",
    "Attract attention from someone dangerous.",
    "Inflict a condition (bleeding, exhausted, shaken, etc.).",
]


VAGUE_PHRASES = (
    "something happens",
    "something bad happens",
    "something mysterious happens",
    "the gm decides",
    "the player loses",
    "the gm chooses",
    "you fail",
    "the worst happens",
)


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    resources: ResourcesDraft,
    categories: AbilityCategoriesDraft,
    overlay: GMOverlay,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> FailureMovesDraft:
    context = {
        "tone_and_pillars": tone.model_dump(),
        "resources": [r.model_dump(exclude_none=True) for r in resources.resources],
        "categories": [c.model_dump(exclude_none=True) for c in categories.categories],
        "npc_conventions": overlay.npc_conventions,
        "example_characters": brief.example_characters,
    }
    draft = call_llm(
        client=client,
        stage_name="failure_moves",
        system_prompt=system_prompt,
        context=context,
        schema=FailureMovesDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
    _validate_move_quality(draft, resources, validation_log)
    return draft


def _validate_move_quality(
    draft: FailureMovesDraft,
    resources: ResourcesDraft,
    validation_log: ValidationLog,
) -> None:
    resource_keys = {r.key for r in resources.resources}
    errors: list[str] = []
    for move in draft.moves:
        haystack = f"{move.title} {move.body}".lower()
        for phrase in VAGUE_PHRASES:
            if phrase in haystack:
                errors.append(
                    f"move {move.title!r} contains vague phrase {phrase!r}; replace with a concrete change"
                )
                break
    references = 0
    if resource_keys:
        pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in resource_keys) + r")\b")
        for move in draft.moves:
            haystack = f"{move.title} {move.body}"
            if pattern.search(haystack):
                references += 1
        if draft.moves and references < max(1, len(draft.moves) // 3):
            errors.append(
                f"only {references}/{len(draft.moves)} failure moves reference a real resource key "
                f"({sorted(resource_keys)}); at least a third should call out a specific resource change"
            )
    if errors:
        for error in errors:
            validation_log.write(f"[failure_moves quality] {error}")
        raise ValueError("failure_moves failed quality validation: " + "; ".join(errors))
