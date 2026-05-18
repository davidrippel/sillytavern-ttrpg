from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import (
    AdvantagesDisadvantagesDraft,
    ComplicationsDraft,
    ExampleHooksDraft,
    GeneratorSeedDraft,
    GMOverlay,
    PackDescription,
    ReviewChecklistDraft,
    ToneAndPillars,
)
from ._common import call_llm

PROMPT_FILE = "11_review_checklist.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    overlay: GMOverlay,
    complications: ComplicationsDraft,
    advantages_disadvantages: AdvantagesDisadvantagesDraft,
    example_hooks: ExampleHooksDraft,
    generator_seed: GeneratorSeedDraft,
    pack_description: PackDescription,
    retries_log: list[dict[str, str | int]],
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> ReviewChecklistDraft:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "overlay_sections": overlay.model_dump(),
        "complication_titles": [c.title for c in complications.complications],
        "success_costs": [s.text for s in complications.success_costs],
        "advantage_axes": [a.title for a in advantages_disadvantages.advantage_axes],
        "disadvantage_axes": [a.title for a in advantages_disadvantages.disadvantage_axes],
        "example_hooks": example_hooks.model_dump(),
        "generator_seed": generator_seed.model_dump(),
        "pack_description": pack_description.description,
        "retries_log": retries_log,
    }
    return call_llm(
        client=client,
        stage_name="review_checklist",
        system_prompt=system_prompt,
        context=context,
        schema=ReviewChecklistDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
