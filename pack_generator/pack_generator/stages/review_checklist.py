from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import (
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
from ._common import call_llm

PROMPT_FILE = "11_review_checklist.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    categories: AbilityCategoriesDraft,
    catalog: AbilityCatalogDraft,
    overlay: GMOverlay,
    failure_moves: FailureMovesDraft,
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
        "attributes": [a.model_dump() for a in attributes.attributes],
        "resources": [r.model_dump(exclude_none=True) for r in resources.resources],
        "categories": [c.model_dump(exclude_none=True) for c in categories.categories],
        "catalog_summary": _catalog_summary(catalog),
        "overlay_sections": overlay.model_dump(),
        "failure_moves": failure_moves.model_dump(),
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


def _catalog_summary(catalog: AbilityCatalogDraft) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ability in catalog.catalog:
        counts[ability.category] = counts.get(ability.category, 0) + 1
    return counts
