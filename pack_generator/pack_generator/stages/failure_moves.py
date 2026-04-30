from __future__ import annotations

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
    return call_llm(
        client=client,
        stage_name="failure_moves",
        system_prompt=system_prompt,
        context=context,
        schema=FailureMovesDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
