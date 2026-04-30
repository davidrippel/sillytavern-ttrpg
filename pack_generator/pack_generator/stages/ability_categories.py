from __future__ import annotations

from common.llm import LLMClient
from common.validation import ValidationLog

from ..brief import GenreBrief
from ..schemas import (
    AbilityCategoriesDraft,
    AttributesDraft,
    ResourcesDraft,
    ToneAndPillars,
)
from ._common import call_llm

PROMPT_FILE = "04_ability_categories.md"


def run(
    *,
    client: LLMClient,
    system_prompt: str,
    brief: GenreBrief,
    tone: ToneAndPillars,
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    model: str,
    temperature: float,
    validation_log: ValidationLog,
) -> AbilityCategoriesDraft:
    context = {
        "brief": {
            "one_line_pitch": brief.one_line_pitch,
            "ability_categories_hint": brief.ability_categories_hint,
            "example_characters": brief.example_characters,
        },
        "tone_and_pillars": tone.model_dump(),
        "attributes": [a.model_dump() for a in attributes.attributes],
        "resources": [r.model_dump(exclude_none=True) for r in resources.resources],
    }
    draft = call_llm(
        client=client,
        stage_name="ability_categories",
        system_prompt=system_prompt,
        context=context,
        schema=AbilityCategoriesDraft,
        model=model,
        temperature=temperature,
        validation_log=validation_log,
    )
    _validate_cross_references(draft, attributes, resources, validation_log)
    return draft


def _validate_cross_references(
    draft: AbilityCategoriesDraft,
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    validation_log: ValidationLog,
) -> None:
    attribute_keys = {a.key for a in attributes.attributes}
    resource_keys = {r.key for r in resources.resources}
    errors: list[str] = []
    for category in draft.categories:
        if category.activation in {"active", "ritual"} and not category.roll_attribute:
            errors.append(f"category {category.key!r} ({category.activation}) requires roll_attribute")
        if category.roll_attribute and category.roll_attribute not in attribute_keys:
            errors.append(
                f"category {category.key!r} roll_attribute {category.roll_attribute!r} is not a known attribute"
            )
        for field in ("consequence_on_failure", "consequence_on_partial"):
            value = getattr(category, field)
            if not value:
                continue
            referenced = value.split(":", 1)[0].strip()
            # Only validate if the value parses as a clean "<resource_key>: ..." reference.
            # Strings that mix resources with prose ("corruption_temporary: +1 OR effect reduced") will
            # contain a colon-prefixed resource we should still recognize.
            if " " in referenced or any(ch in referenced for ch in "+-*/"):
                continue
            if referenced and referenced not in resource_keys:
                errors.append(
                    f"category {category.key!r} {field} references unknown resource {referenced!r}"
                )
    if errors:
        for error in errors:
            validation_log.write(f"[ability_categories cross-ref] {error}")
        raise ValueError("ability_categories failed cross-reference validation: " + "; ".join(errors))
