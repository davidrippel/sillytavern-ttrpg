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
    _validate_cross_references(draft, attributes, resources, validation_log, brief=brief)
    return draft


WEIRD_HINT_TERMS = (
    "weird",
    "magic",
    "psionic",
    "hacking",
    "cyberware",
    "alien tech",
    "sorcery",
    "occult",
    "supernatural",
    "ritual",
    "genre-defining",
    "signature power",
)


def _validate_cross_references(
    draft: AbilityCategoriesDraft,
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    validation_log: ValidationLog,
    *,
    brief: GenreBrief | None = None,
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
    referenced_resources: set[str] = set()
    for category in draft.categories:
        for field in ("consequence_on_failure", "consequence_on_partial"):
            value = getattr(category, field)
            if not value:
                continue
            referenced = value.split(":", 1)[0].strip()
            if referenced in resource_keys:
                referenced_resources.add(referenced)
    live_kinds = {"pool", "pool_with_threshold", "counter", "tally"}
    threshold_targets: set[str] = set()
    for resource in resources.resources:
        if resource.threshold_field:
            threshold_targets.add(resource.threshold_field)
        consequence = resource.threshold_consequence or {}
        target = consequence.get("field") if isinstance(consequence, dict) else None
        if isinstance(target, str):
            threshold_targets.add(target)
    static_support: set[str] = set()
    for resource in resources.resources:
        if resource.max_value_field:
            static_support.add(resource.max_value_field)
        if resource.threshold_field:
            static_support.add(resource.threshold_field)
    for resource in resources.resources:
        if resource.key in {"hp_current", "hp_max"}:
            continue
        if resource.kind not in live_kinds:
            if resource.key in static_support:
                continue
            errors.append(
                f"resource {resource.key!r} has kind {resource.kind!r} but is not referenced as a "
                f"max_value_field or threshold_field by any live resource — looks inert"
            )
            continue
        ticks_from_threshold = resource.key in threshold_targets
        ticks_from_ability = resource.key in referenced_resources
        if not (ticks_from_threshold or ticks_from_ability):
            errors.append(
                f"resource {resource.key!r} ({resource.kind}) is not referenced by any ability category "
                f"consequence and has no threshold_consequence targeting it — orphan resource that never "
                f"ticks in play"
            )
    if brief is not None and brief.ability_categories_hint:
        hint_lower = brief.ability_categories_hint.lower()
        if any(term in hint_lower for term in WEIRD_HINT_TERMS):
            non_hp_resources = {r.key for r in resources.resources} - {"hp_current", "hp_max"}
            has_weird_category = False
            for category in draft.categories:
                for field in ("consequence_on_failure", "consequence_on_partial"):
                    value = getattr(category, field)
                    if not value:
                        continue
                    referenced = value.split(":", 1)[0].strip()
                    if referenced in non_hp_resources:
                        has_weird_category = True
                        break
                if has_weird_category:
                    break
            if not has_weird_category:
                errors.append(
                    f"the brief hints at a 'weird'/genre-defining category but no ability category "
                    f"references a non-HP resource as a consequence; the genre-defining category should "
                    f"have a genre-defining cost (e.g. magic costs corruption, hacking costs heat)"
                )
    if errors:
        for error in errors:
            validation_log.write(f"[ability_categories cross-ref] {error}")
        raise ValueError("ability_categories failed cross-reference validation: " + "; ".join(errors))
