from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from common.pack import load_pack

from .schemas import (
    AdvantagesDisadvantagesDraft,
    ComplicationsDraft,
    ExampleHooksDraft,
    GeneratorSeedDraft,
    GMOverlay,
    NamingDraft,
    ReviewChecklistDraft,
    ToneAndPillars,
    UNIVERSAL_COMPLICATIONS,
)


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

    Newlines that separate paragraphs (preceded/followed by another
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


def render_pack_yaml(metadata: dict[str, Any]) -> str:
    payload = dict(metadata)
    if isinstance(payload.get("description"), str):
        payload["description"] = _wrap_long(payload["description"])
    return _yaml_dump_with_blocks(payload)


def render_naming_yaml(naming: NamingDraft) -> str:
    payload = {
        "naming_registers": [_wrap_long(entry) for entry in naming.naming_registers],
        "district_flavors": [_wrap_long(entry) for entry in naming.district_flavors],
    }
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
        ("Resolving actions — narrative, no dice", overlay.resolving_actions),
        ("Translating mechanical pressures into fiction", overlay.translating_pressures),
        ("NPC conventions", overlay.npc_conventions),
        ("Content to include", overlay.content_to_include),
        ("Content to avoid", overlay.content_to_avoid),
        ("Character creation", overlay.character_creation),
    ]
    parts: list[str] = []
    for title, body in sections:
        body = _unwrap_prose(body or "").strip()
        if not body:
            continue
        parts.append(f"## {title}\n\n{body}")
    return "\n\n".join(parts) + "\n"


def render_complications_md(pack_display_name: str, draft: ComplicationsDraft) -> str:
    lines: list[str] = [f"## {pack_display_name} complications", ""]
    lines.append(
        "When an action goes badly — disadvantage in play, the situation hostile, or a moment of bad luck "
        "demanded by the fiction — pick one or more from this list. Universal moves from the engine are "
        "marked `[universal]`. These are narrative consequences, not table rolls."
    )
    lines.append("")
    for entry in draft.complications:
        body = _unwrap_prose(entry.body)
        lines.append(f"- **{entry.title}** {body}")
    for universal in UNIVERSAL_COMPLICATIONS:
        lines.append(f"- `[universal]` {universal}")
    lines.append("")
    lines.append("## When the action succeeds but the world still pushes back")
    lines.append("")
    lines.append(
        "A clean win is rare. When an action succeeds, choose a cost that lets the success stand "
        "but bills the protagonist for it:"
    )
    lines.append("")
    for cost in draft.success_costs:
        lines.append(f"- {_unwrap_prose(cost.text)}")
    return "\n".join(lines).rstrip() + "\n"


def render_advantages_disadvantages_md(
    pack_display_name: str, draft: AdvantagesDisadvantagesDraft
) -> str:
    lines: list[str] = [
        f"## Advantages and disadvantages — {pack_display_name} vocabulary",
        "",
        (
            "This document is reference material for the GM (embedded into the lorebook as "
            "`__pack_reference`), the extension's character-sheet UI (autocomplete), and the "
            "campaign generator (sample characters). A story-mode character has 2–3 "
            "advantages and 1–2 disadvantages. Each is a short phrase the GM can recognize "
            "and lean on. Specific beats generic."
        ),
        "",
        "### Advantages",
        "",
    ]
    for axis in draft.advantage_axes:
        lines.append(f"**{axis.title}**")
        lines.append("")
        for entry in axis.entries:
            lines.append(f"- {entry}")
        lines.append("")
    lines.append("### Disadvantages")
    lines.append("")
    for axis in draft.disadvantage_axes:
        lines.append(f"**{axis.title}**")
        lines.append("")
        for entry in axis.entries:
            lines.append(f"- {entry}")
        lines.append("")
    lines.append("### Style")
    lines.append("")
    lines.append(
        "Each entry should name a specific thing the GM can picture (a place, training, mark, "
        "or debt), be invocable by the player (\"this is in play\"), cut both ways when "
        "appropriate, and stay grounded in the genre. Players and the campaign generator may "
        "invent new entries that fit the same shape."
    )
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
    character_template: dict[str, Any],
    overlay: GMOverlay,
    tone: ToneAndPillars,
    inspirations_text: str | None,
    complications: ComplicationsDraft,
    advantages_disadvantages: AdvantagesDisadvantagesDraft,
    example_hooks: ExampleHooksDraft,
    generator_seed: GeneratorSeedDraft,
    checklist: ReviewChecklistDraft,
    naming: NamingDraft,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "pack.yaml").write_text(render_pack_yaml(pack_metadata), encoding="utf-8")
    (output_dir / "character_template.json").write_text(
        render_character_template_json(character_template), encoding="utf-8"
    )
    (output_dir / "gm_prompt_overlay.md").write_text(
        render_gm_overlay_md(overlay), encoding="utf-8"
    )
    (output_dir / "tone.md").write_text(render_tone_md(tone, inspirations_text), encoding="utf-8")
    (output_dir / "complications.md").write_text(
        render_complications_md(pack_metadata["display_name"], complications), encoding="utf-8"
    )
    (output_dir / "advantages_disadvantages.md").write_text(
        render_advantages_disadvantages_md(
            pack_metadata["display_name"], advantages_disadvantages
        ),
        encoding="utf-8",
    )
    (output_dir / "example_hooks.md").write_text(
        render_example_hooks_md(example_hooks), encoding="utf-8"
    )
    (output_dir / "generator_seed.yaml").write_text(
        render_generator_seed_yaml(generator_seed, pack_metadata["pack_name"]), encoding="utf-8"
    )
    (output_dir / "naming.yaml").write_text(render_naming_yaml(naming), encoding="utf-8")
    (output_dir / "REVIEW_CHECKLIST.md").write_text(
        render_review_checklist_md(pack_metadata["display_name"], checklist), encoding="utf-8"
    )


def validate_written_pack(output_dir: Path) -> None:
    """Final spec-level validation. Raises PackValidationError on failure."""
    load_pack(output_dir)
