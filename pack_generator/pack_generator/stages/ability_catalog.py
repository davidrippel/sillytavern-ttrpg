from __future__ import annotations

from collections import Counter

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import (
    AbilityCatalogDraft,
    AbilityCategoriesDraft,
    AttributesDraft,
    ResourcesDraft,
    ToneAndPillars,
)
from ._common import call_llm

PROMPT_FILE = "05_ability_catalog.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    categories: AbilityCategoriesDraft,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> AbilityCatalogDraft:
    context = {
        "brief": {
            "example_characters": brief.example_characters,
            "ability_categories_hint": brief.ability_categories_hint,
        },
        "tone_and_pillars": tone.model_dump(),
        "attributes": [a.model_dump() for a in attributes.attributes],
        "resources": [r.model_dump(exclude_none=True) for r in resources.resources],
        "categories": [c.model_dump(exclude_none=True) for c in categories.categories],
    }
    draft = call_llm(
        client=client,
        stage_name="ability_catalog",
        system_prompt=system_prompt,
        context=context,
        schema=AbilityCatalogDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
    _validate_distribution(draft, categories, validation_log)
    return draft


def _validate_distribution(
    draft: AbilityCatalogDraft,
    categories: AbilityCategoriesDraft,
    validation_log: ValidationLog,
) -> None:
    category_keys = {c.key for c in categories.categories}
    counts = Counter(a.category for a in draft.catalog)
    errors: list[str] = []
    unknown = sorted(set(counts) - category_keys)
    if unknown:
        errors.append(f"abilities reference unknown categories: {unknown}")
    for category_key in category_keys:
        n = counts.get(category_key, 0)
        if n < 2:
            errors.append(f"category {category_key!r} has {n} abilities (need at least 2)")
        if n > 8:
            errors.append(f"category {category_key!r} has {n} abilities (cap is 8)")
    if errors:
        for error in errors:
            validation_log.write(f"[ability_catalog distribution] {error}")
        raise ValueError("ability_catalog failed distribution validation: " + "; ".join(errors))
