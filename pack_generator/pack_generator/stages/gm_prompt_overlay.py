from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import (
    AbilityCatalogDraft,
    AbilityCategoriesDraft,
    AttributesDraft,
    GMOverlay,
    ResourcesDraft,
    ToneAndPillars,
)
from ._common import call_llm

PROMPT_FILE = "06_gm_prompt_overlay.md"


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
    model: str,
    temperature: float,
    validation_log: ValidationLog,
    max_repair_passes: int = 1,
) -> GMOverlay:
    context = {
        "brief": brief.model_dump(exclude_none=True),
        "tone_and_pillars": tone.model_dump(),
        "attributes": [a.model_dump() for a in attributes.attributes],
        "resources": [r.model_dump(exclude_none=True) for r in resources.resources],
        "categories": [c.model_dump(exclude_none=True) for c in categories.categories],
        "ability_catalog_size": len(catalog.catalog),
    }
    overlay = call_llm(
        client=client,
        stage_name="gm_prompt_overlay",
        system_prompt=system_prompt,
        context=context,
        schema=GMOverlay,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )

    for attempt in range(1, max_repair_passes + 1):
        gaps = _find_reference_gaps(overlay, attributes, resources, categories)
        if not gaps:
            return overlay
        validation_log.write(
            f"[gm_prompt_overlay] repair pass {attempt}: missing references in sections: {gaps}"
        )
        repair_context = {
            **context,
            "previous_overlay": overlay.model_dump(),
            "missing_references": gaps,
            "instructions": (
                "The overlay you produced is missing required references. Add the missing items to "
                "their respective sections. Do not remove existing content — extend it. Keep the "
                "no-hard-line-wrap rule and the under-1500-words guideline."
            ),
        }
        overlay = call_llm(
            client=client,
            stage_name="gm_prompt_overlay",
            system_prompt=system_prompt,
            context=repair_context,
            schema=GMOverlay,
            model=model,
            temperature=temperature,
            validation_log=validation_log,
        )

    final_gaps = _find_reference_gaps(overlay, attributes, resources, categories)
    if final_gaps:
        for gap_section, missing in final_gaps.items():
            validation_log.write(f"[gm_prompt_overlay] still missing in {gap_section}: {missing}")
        raise ValueError(
            "gm_prompt_overlay failed reference-coverage validation after repair: " + str(final_gaps)
        )
    return overlay


def _find_reference_gaps(
    overlay: GMOverlay,
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    categories: AbilityCategoriesDraft,
) -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {}
    attribute_section = overlay.attribute_guidance.lower()
    missing_attributes = [
        a.display
        for a in attributes.attributes
        if a.display.lower() not in attribute_section and a.key not in attribute_section
    ]
    if missing_attributes:
        gaps["attribute_guidance"] = missing_attributes

    resource_section = overlay.resource_mechanics.lower()
    missing_resources = [
        r.key
        for r in resources.resources
        if r.key not in resource_section and r.display.lower() not in resource_section
    ]
    if missing_resources:
        gaps["resource_mechanics"] = missing_resources

    ability_section = overlay.ability_adjudication.lower()
    missing_categories = [
        c.key
        for c in categories.categories
        if c.key not in ability_section and c.display.lower() not in ability_section
    ]
    if missing_categories:
        gaps["ability_adjudication"] = missing_categories

    return gaps
