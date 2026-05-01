from __future__ import annotations

from pathlib import Path

from common.pack import GenrePack


def build_seed_template(pack: GenrePack) -> str:
    defaults = pack.generator_seed_defaults
    antagonist_menu = defaults.get("antagonist_archetypes_preferred", [])
    antagonist_example = antagonist_menu[0] if antagonist_menu else "<archetype_from_pack>"

    lines = [
        "# Blank campaign seed template.",
        "# Field documentation: Docs/09_SEED_FORMAT.md",
        "",
        "# Required: must match the target pack's pack_name.",
        f"genre: {pack.metadata.pack_name}",
        "",
        "# Optional but high-leverage: one paragraph describing the campaign.",
        "# campaign_pitch: >",
        "#   One or two sentences naming the central tension, the protagonist's stake,",
        "#   and the world detail that makes this campaign specific.",
        "",
        "# Optional: themes to weave through the campaign.",
        "# themes_include:",
        "#   - <theme_one>",
        "#   - <theme_two>",
        "",
        "# Optional: themes to avoid. Merges with pack defaults.",
        "# themes_exclude:",
        "#   - <theme_to_avoid>",
        "",
        "# Optional: rough shape of the protagonist.",
        "# protagonist_archetype: >",
        "#   A short phrase describing the protagonist's role in this world.",
        "",
        "# Optional: facts the protagonist already knows.",
        "# protagonist_known_facts:",
        "#   - <a fact the protagonist already knows at game start>",
        "",
        "# Optional: specific places or objects anchoring the campaign.",
        "# setting_anchors:",
        "#   - <anchor_one>",
        "#   - <anchor_two>",
        "",
        "# Optional: preferred antagonist archetypes.",
        f"# Available in this pack: {', '.join(antagonist_menu) if antagonist_menu else 'none listed'}",
        "# antagonist_archetypes_preferred:",
        f"#   - {antagonist_example}",
        "",
        "# Optional: explicit first-scene seed.",
        "# opening_hook_seed: >",
        "#   One sentence describing the inciting moment that opens play.",
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
