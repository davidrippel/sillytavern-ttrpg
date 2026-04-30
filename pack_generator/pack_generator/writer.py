from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from common.pack import load_pack

from .schemas import (
    AbilityCatalogDraft,
    AbilityCategoriesDraft,
    AttributesDraft,
    ExampleHooksDraft,
    FailureMovesDraft,
    GeneratorSeedDraft,
    GMOverlay,
    ResourcesDraft,
    ReviewChecklistDraft,
    ToneAndPillars,
)
from .stages.failure_moves import UNIVERSAL_MOVES


_BLOCK_SCALAR_THRESHOLD = 80


class _LiteralStr(str):
    """Marker so PyYAML emits long strings as folded block scalars."""


def _literal_presenter(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.Nodes:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style=">")


yaml.add_representer(_LiteralStr, _literal_presenter)


def _wrap_long(value: str) -> Any:
    cleaned = _unwrap_prose(value)
    if len(cleaned) >= _BLOCK_SCALAR_THRESHOLD:
        return _LiteralStr(cleaned)
    return cleaned


def _unwrap_prose(value: str) -> str:
    """Defensively undo any column wrapping the LLM may have applied.

    Newlines that separate paragraphs (i.e. preceded/followed by another
    newline) are preserved; single newlines inside a paragraph are
    converted to spaces.
    """
    if not value:
        return value
    lines = value.split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    for line in lines:
        if line.strip() == "":
            if paragraph:
                out.append(" ".join(paragraph).strip())
                paragraph = []
            out.append("")
        else:
            paragraph.append(line.strip())
    if paragraph:
        out.append(" ".join(paragraph).strip())
    # Collapse runs of blank lines.
    cleaned: list[str] = []
    for line in out:
        if line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _yaml_dump(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=10_000)


def _yaml_dump_with_blocks(payload: dict[str, Any]) -> str:
    return yaml.dump(payload, sort_keys=False, allow_unicode=True, width=10_000)


def render_attributes_yaml(attributes: AttributesDraft) -> str:
    payload = {
        "attributes": [
            {
                "key": a.key,
                "display": a.display,
                "description": _wrap_long(a.description),
                "examples": list(a.examples),
            }
            for a in attributes.attributes
        ]
    }
    return _yaml_dump_with_blocks(payload)


def render_resources_yaml(resources: ResourcesDraft) -> str:
    items: list[dict[str, Any]] = []
    for r in resources.resources:
        entry: dict[str, Any] = {"key": r.key, "display": r.display, "kind": r.kind}
        if r.description is not None:
            entry["description"] = _wrap_long(r.description)
        if r.starting_value is not None:
            entry["starting_value"] = r.starting_value
        if r.max_value_field:
            entry["max_value_field"] = r.max_value_field
        if r.threshold_field:
            entry["threshold_field"] = r.threshold_field
        if r.threshold_consequence:
            entry["threshold_consequence"] = r.threshold_consequence
        if r.threshold is not None:
            entry["threshold"] = r.threshold
        if r.threshold_effect:
            entry["threshold_effect"] = r.threshold_effect
        if r.endgame_value is not None:
            entry["endgame_value"] = r.endgame_value
        if r.endgame_effect:
            entry["endgame_effect"] = r.endgame_effect
        # Preserve any additional fields the LLM included.
        extras = r.model_dump(exclude_none=True)
        for key, value in extras.items():
            if key not in entry:
                entry[key] = value
        items.append(entry)
    return _yaml_dump_with_blocks({"resources": items})


def render_abilities_yaml(categories: AbilityCategoriesDraft, catalog: AbilityCatalogDraft) -> str:
    cat_items: list[dict[str, Any]] = []
    for c in categories.categories:
        entry: dict[str, Any] = {
            "key": c.key,
            "display": c.display,
            "description": _wrap_long(c.description),
            "activation": c.activation,
        }
        if c.roll_attribute:
            entry["roll_attribute"] = c.roll_attribute
        if c.consequence_on_failure:
            entry["consequence_on_failure"] = c.consequence_on_failure
        if c.consequence_on_partial:
            entry["consequence_on_partial"] = c.consequence_on_partial
        entry["has_levels"] = c.has_levels
        if c.has_levels and c.level_names:
            entry["level_names"] = list(c.level_names)
        cat_items.append(entry)
    catalog_items: list[dict[str, Any]] = []
    for a in catalog.catalog:
        catalog_items.append(
            {
                "name": a.name,
                "category": a.category,
                "prerequisite": a.prerequisite or "none",
                "description": _wrap_long(a.description),
                "effect": _wrap_long(a.effect),
            }
        )
    return _yaml_dump_with_blocks({"categories": cat_items, "catalog": catalog_items})


def render_pack_yaml(metadata: dict[str, Any]) -> str:
    payload = dict(metadata)
    if isinstance(payload.get("description"), str):
        payload["description"] = _wrap_long(payload["description"])
    return _yaml_dump_with_blocks(payload)


def render_generator_seed_yaml(seed: GeneratorSeedDraft, pack_name: str) -> str:
    payload = {"genre": pack_name, **seed.model_dump()}
    return _yaml_dump(payload)


def render_character_template_json(template: dict[str, Any]) -> str:
    return json.dumps(template, indent=2, ensure_ascii=False) + "\n"


def render_gm_overlay_md(overlay: GMOverlay) -> str:
    sections = [
        ("Setting and tone", overlay.setting_and_tone),
        ("Thematic pillars", overlay.thematic_pillars),
        ("Attribute guidance", overlay.attribute_guidance),
        ("Resource mechanics", overlay.resource_mechanics),
        ("Ability adjudication", overlay.ability_adjudication),
        ("Genre-specific NPC conventions", overlay.npc_conventions),
        ("Content to include", overlay.content_to_include),
        ("Content to avoid", overlay.content_to_avoid),
        ("Character creation", overlay.character_creation),
    ]
    parts: list[str] = []
    for title, body in sections:
        body = _unwrap_prose(body)
        parts.append(f"## {title}\n\n{body}")
    return "\n\n".join(parts) + "\n"


def render_failure_moves_md(pack_display_name: str, moves: FailureMovesDraft) -> str:
    lines: list[str] = [f"## {pack_display_name} failure moves (2-6)", ""]
    lines.append(
        "On a failure, the GM chooses one or more from this list. Universal moves from the engine are marked `[universal]`."
    )
    lines.append("")
    for move in moves.moves:
        body = _unwrap_prose(move.body)
        lines.append(f"- **{move.title}** {body}")
    for universal in UNIVERSAL_MOVES:
        lines.append(f"- `[universal]` {universal}")
    lines.append("")
    lines.append("## Partial success (7-9) trades")
    lines.append("")
    lines.append("On a partial, offer the player a choice or impose a clear cost:")
    lines.append("")
    for trade in moves.partial_success_trades:
        lines.append(f"- {_unwrap_prose(trade)}")
    return "\n".join(lines).rstrip() + "\n"


def render_example_hooks_md(hooks: ExampleHooksDraft) -> str:
    parts: list[str] = []
    for index, hook in enumerate(hooks.hooks, start=1):
        body = _unwrap_prose(hook.body)
        parts.append(f"## Hook {index}: {hook.title}\n\n{body}")
    return ("\n\n---\n\n".join(parts)) + "\n"


def render_tone_md(tone: ToneAndPillars, brief_inspirations: str | None) -> str:
    setting = _unwrap_prose(tone.setting_statement)
    lines = [
        "## Mood",
        "",
        setting,
    ]
    if tone.pillars:
        lines += ["", "## Thematic pillars", ""]
        for pillar in tone.pillars:
            description = _unwrap_prose(pillar.description)
            lines.append(f"- **{pillar.title}.** {description}")
    if brief_inspirations:
        lines += ["", "## Reference stack", "", _unwrap_prose(brief_inspirations)]
    return "\n".join(lines).rstrip() + "\n"


def render_review_checklist_md(pack_display_name: str, checklist: ReviewChecklistDraft) -> str:
    by_section: dict[str, list[str]] = {}
    for item in checklist.items:
        by_section.setdefault(item.section, []).append(_unwrap_prose(item.text))
    lines = [f"## Review checklist for {pack_display_name}", ""]
    for section, items in by_section.items():
        lines.append(f"### {section}")
        lines.append("")
        for text in items:
            lines.append(f"- [ ] {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_pack_files(
    *,
    output_dir: Path,
    pack_metadata: dict[str, Any],
    attributes: AttributesDraft,
    resources: ResourcesDraft,
    categories: AbilityCategoriesDraft,
    catalog: AbilityCatalogDraft,
    character_template: dict[str, Any],
    overlay: GMOverlay,
    tone: ToneAndPillars,
    inspirations_text: str | None,
    failure_moves: FailureMovesDraft,
    example_hooks: ExampleHooksDraft,
    generator_seed: GeneratorSeedDraft,
    checklist: ReviewChecklistDraft,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "pack.yaml").write_text(render_pack_yaml(pack_metadata), encoding="utf-8")
    (output_dir / "attributes.yaml").write_text(render_attributes_yaml(attributes), encoding="utf-8")
    (output_dir / "resources.yaml").write_text(render_resources_yaml(resources), encoding="utf-8")
    (output_dir / "abilities.yaml").write_text(render_abilities_yaml(categories, catalog), encoding="utf-8")
    (output_dir / "character_template.json").write_text(
        render_character_template_json(character_template), encoding="utf-8"
    )
    (output_dir / "gm_prompt_overlay.md").write_text(render_gm_overlay_md(overlay), encoding="utf-8")
    (output_dir / "tone.md").write_text(render_tone_md(tone, inspirations_text), encoding="utf-8")
    (output_dir / "failure_moves.md").write_text(
        render_failure_moves_md(pack_metadata["display_name"], failure_moves), encoding="utf-8"
    )
    (output_dir / "example_hooks.md").write_text(
        render_example_hooks_md(example_hooks), encoding="utf-8"
    )
    (output_dir / "generator_seed.yaml").write_text(
        render_generator_seed_yaml(generator_seed, pack_metadata["pack_name"]), encoding="utf-8"
    )
    (output_dir / "REVIEW_CHECKLIST.md").write_text(
        render_review_checklist_md(pack_metadata["display_name"], checklist), encoding="utf-8"
    )


def validate_written_pack(output_dir: Path) -> None:
    """Final spec-level validation. Raises PackValidationError on failure."""
    load_pack(output_dir)
