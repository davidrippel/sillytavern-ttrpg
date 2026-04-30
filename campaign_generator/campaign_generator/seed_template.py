from __future__ import annotations

from pathlib import Path

from common.pack import GenrePack


def build_seed_template(pack: GenrePack) -> str:
    defaults = pack.generator_seed_defaults
    antagonist_menu = defaults.get("antagonist_archetypes_preferred", [])

    lines = [
        "# Blank campaign seed template.",
        "# Field documentation: Docs/09_SEED_FORMAT.md",
        "",
        "# Required: must match the target pack's pack_name.",
        f"genre: {pack.metadata.pack_name}",
        "",
        "# Optional but high-leverage: one paragraph describing the campaign.",
        "# campaign_pitch: >",
        "#   A missing mentor, a frontier town hiding something, and a forest that watches.",
        "",
        "# Optional: themes to weave through the campaign.",
        "# themes_include:",
        "#   - a_mentor's_last_secret",
        "#   - trust_in_institutions_eroding",
        "",
        "# Optional: themes to avoid. Merges with pack defaults.",
        "# themes_exclude:",
        "#   - romance",
        "",
        "# Optional: rough shape of the protagonist.",
        "# protagonist_archetype: >",
        "#   A hedge witch, scout, scholar, or other lore-facing outsider.",
        "",
        "# Optional: facts the protagonist already knows.",
        "# protagonist_known_facts:",
        "#   - Their mentor vanished near Davokar.",
        "",
        "# Optional: specific places or objects anchoring the campaign.",
        "# setting_anchors:",
        "#   - thistle_hold",
        "#   - davokar_forest",
        "",
        "# Optional: preferred antagonist archetypes.",
        f"# Available in this pack: {', '.join(antagonist_menu) if antagonist_menu else 'none listed'}",
        "# antagonist_archetypes_preferred:",
        "#   - corrupt_inquisitor",
        "",
        "# Optional: explicit first-scene seed.",
        "# opening_hook_seed: >",
        "#   A raven-delivered summons drags the protagonist back to Thistle Hold.",
        "",
        "# Optional: tone dials layered on top of the pack tone.",
        "# tone_modifiers:",
        "#   - investigative_rather_than_action_heavy",
        "",
        "# Optional structural controls.",
        "# num_acts: 4",
        "# num_npcs: 10",
        "# num_locations: 8",
        "# clue_chain_density: medium",
        "# branch_points: 7",
        "",
        "# Optional generation controls.",
        "# random_seed: 12345",
        "# model: openai/gpt-4o-mini",
        "# temperature: 0.8",
        "",
        "# Optional strictness overrides. Merges field-by-field with pack defaults.",
        "# strictness:",
        "#   clue_graph_connectivity: strict",
        "#   npc_voice_diversity: strict",
        "#   canon_consistency: strict",
        "",
    ]
    return "\n".join(lines)


def write_seed_template(output_path: str | Path, pack: GenrePack) -> Path:
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_seed_template(pack), encoding="utf-8")
    return destination
