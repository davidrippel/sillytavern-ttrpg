from __future__ import annotations

import re
from typing import Any

from common.pack import GenrePack
from .schemas import BranchPlan, ClueGraph, FactionSet, LocationCatalog, NPCRoster, PlotSkeleton, PremiseDocument, SampleCharacterSet


_HONORIFICS = {
    "sister", "brother", "father", "mother",
    "lord", "lady", "sir", "dame",
    "captain", "marshal", "foreman",
    "master", "mistress", "magister", "inquisitor",
    "baron", "baroness", "count", "countess",
    "duke", "duchess", "king", "queen", "prince", "princess",
    "saint", "elder", "high",
}

_ARTICLES = {"the", "a", "an"}

_STOPWORD_KEYS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "at",
    "by", "for", "with", "from", "as", "is", "it",
    "tavern", "church", "temple", "shrine", "guild", "house",
    "family", "order", "company",
}


def _strip_parenthetical(name: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*(.*)$", name)
    if not match:
        return name.strip(), None
    head = (match.group(1) + " " + match.group(3)).strip()
    inside = match.group(2).strip() or None
    return head, inside


def _drop_leading_article(name: str) -> str:
    parts = name.split(None, 1)
    if len(parts) == 2 and parts[0].lower() in _ARTICLES:
        return parts[1]
    return name


def _strip_leading_honorifics(name: str) -> str:
    tokens = name.split()
    while tokens and tokens[0].lower() in _HONORIFICS:
        tokens = tokens[1:]
    return " ".join(tokens)


def _generate_short_forms(name: str) -> list[str]:
    """Personal-name short forms after honorifics (e.g. 'Sister Valeria' → 'Valeria',
    'Lord Cassius Valerius' → 'Cassius', 'Cassius Valerius')."""
    after_titles = _strip_leading_honorifics(name)
    if not after_titles or after_titles == name.strip():
        return []
    tokens = after_titles.split()
    forms: list[str] = []
    if tokens:
        forms.append(tokens[0])
    if len(tokens) > 1:
        forms.append(after_titles)
    return forms


def _strip_trailing_type_token(name: str, type_value: str | None) -> str | None:
    if not type_value:
        return None
    type_tokens = {token.lower() for token in re.findall(r"[A-Za-z]+", type_value)}
    if not type_tokens:
        return None
    tokens = name.split()
    if len(tokens) < 2:
        return None
    if tokens[-1].lower() in type_tokens:
        return " ".join(tokens[:-1])
    return None


def _is_acceptable(variant: str) -> bool:
    stripped = variant.strip()
    if len(stripped) < 3:
        return False
    if stripped.lower() in _STOPWORD_KEYS:
        return False
    return True


def _name_variants(name: str, *, type_hint: str | None = None) -> list[str]:
    """Trigger keys for SillyTavern. ST does substring matching; we emit the full
    name plus likely short forms a player would actually type — first names after
    honorifics, article-stripped variants, parenthetical-stripped variants, and
    (for locations) the bare name without a generic type suffix."""
    base = name.strip()
    if not base:
        return []

    candidates: list[str] = [base]

    head, inside = _strip_parenthetical(base)
    if head and head != base:
        candidates.append(head)
    if inside:
        candidates.append(inside)

    expanded: list[str] = []
    for candidate in candidates:
        expanded.append(candidate)
        no_article = _drop_leading_article(candidate)
        if no_article != candidate:
            expanded.append(no_article)
        for short in _generate_short_forms(no_article):
            expanded.append(short)
        trimmed = _strip_trailing_type_token(no_article, type_hint)
        if trimmed:
            expanded.append(trimmed)
            for short in _generate_short_forms(trimmed):
                expanded.append(short)
        if "," in candidate:
            expanded.append(candidate.split(",", 1)[0].strip())

    seen: list[str] = []
    for variant in expanded:
        cleaned = variant.strip()
        if not _is_acceptable(cleaned):
            continue
        if cleaned in seen:
            continue
        seen.append(cleaned)
    return seen


def _entry(
    uid: int,
    *,
    comment: str,
    content: str,
    keys: list[str] | None = None,
    secondary_keys: list[str] | None = None,
    constant: bool = False,
    selective: bool | None = None,
    order: int = 100,
    disable: bool = False,
) -> dict[str, Any]:
    keys = keys or []
    if selective is None:
        selective = bool(keys) and not constant
    return {
        "uid": uid,
        "key": keys,
        "keysecondary": secondary_keys or [],
        "comment": comment,
        "content": content,
        "constant": constant,
        "vectorized": False,
        "selective": selective,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": 0,
        "disable": disable,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": 0,
        "probability": 100,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 0,
        "sticky": None,
        "cooldown": None,
        "delay": None,
        "displayIndex": uid - 1,
    }


def assemble_lorebook(
    *,
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    factions: FactionSet,
    npcs: NPCRoster,
    locations: LocationCatalog,
    clue_graph: ClueGraph,
    branches: BranchPlan,
    sample_characters: SampleCharacterSet | None = None,
) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    uid = 0

    def add(entry: dict[str, Any]) -> None:
        entries[str(entry["uid"])] = entry

    uid += 1
    add(
        _entry(
            uid,
            comment="GM Prompt Overlay",
            content=pack.gm_prompt_overlay,
            constant=True,
            order=1000,
        )
    )

    uid += 1
    add(
        _entry(
            uid,
            comment="Failure Moves",
            content=pack.failure_moves,
            constant=True,
            order=950,
        )
    )

    uid += 1
    add(
        _entry(
            uid,
            comment=f"Pack Reference: {pack.metadata.display_name}",
            content=(
                f'{{"pack_name":"{pack.metadata.pack_name}","pack_version":"{pack.metadata.version}",'
                f'"display_name":"{pack.metadata.display_name}"}}'
            ),
            constant=False,
            selective=False,
            order=0,
        )
    )

    title = (premise.title or pack.metadata.display_name).strip()
    campaign_bible = "\n\n".join(
        [
            premise.premise_text,
            f"Central conflict: {premise.central_conflict}",
            f"Tone: {premise.tone_statement}",
            "Themes:\n" + "\n".join(f"- {theme}" for theme in premise.thematic_pillars),
        ]
    )
    uid += 1
    add(
        _entry(
            uid,
            comment=f"Campaign Bible: {title}",
            content=campaign_bible,
            constant=True,
            order=900,
        )
    )

    for act_index, act in enumerate(plot.acts):
        act_content = "\n\n".join(
            [
                f"Act {act.act_number}: {act.title}",
                f"Goal: {act.goal}",
                "Beats:\n" + "\n".join(f"- {beat.rendered}" for beat in act.beats),
            ]
        )
        beat_labels = [beat.label for beat in act.beats if beat.label]
        act_keys = [act.title, f"Act {act.act_number}", *beat_labels]
        is_first_act = act_index == 0
        comment = (
            f"Current Act: {act.title}" if is_first_act else f"Act {act.act_number}: {act.title}"
        )
        uid += 1
        add(
            _entry(
                uid,
                comment=comment,
                content=act_content,
                keys=act_keys,
                constant=is_first_act,
                order=850 - act_index,
            )
        )

    for faction in factions.factions:
        content = "\n\n".join(
            [
                f"Faction: {faction.name}",
                faction.description,
                f"Goals: {', '.join(faction.goals)}",
                f"Methods: {', '.join(faction.methods)}",
                f"Internal tensions: {', '.join(faction.internal_tensions)}",
                f"Plot role: {faction.relationship_to_plot}",
            ]
        )
        uid += 1
        add(
            _entry(
                uid,
                comment=f"Faction: {faction.name}",
                content=content,
                keys=_name_variants(faction.name),
                order=500,
            )
        )

    for npc in npcs.npcs:
        relationships = ", ".join(f"{rel.name} ({rel.description})" for rel in npc.relationships) or "none recorded"
        public_content = "\n".join(
            [
                f"Name: {npc.name}",
                f"Role: {npc.role}",
                f"Faction: {npc.faction_affiliation or 'independent'}",
                f"Description: {npc.physical_description}",
                f"Voice: {npc.speaking_style}",
                f"Motivation: {npc.motivation}",
                f"Relationships: {relationships}",
                f"Abilities: {', '.join(npc.abilities) if npc.abilities else 'none'}",
            ]
        )
        uid += 1
        add(
            _entry(
                uid,
                comment=f"NPC: {npc.name}",
                content=public_content,
                keys=_name_variants(npc.name),
                order=450,
            )
        )

        secret_text = (npc.secret or "").strip()
        if secret_text:
            secret_content = "\n".join(
                [
                    f"Hidden truth — {npc.name}",
                    "(GM-only. Reveal only when the campaign reaches the moment this becomes earned. Enable this entry by setting disable=false once the reveal lands.)",
                    "",
                    secret_text,
                ]
            )
            uid += 1
            add(
                _entry(
                    uid,
                    comment=f"NPC Secret: {npc.name}",
                    content=secret_content,
                    keys=[],
                    selective=False,
                    constant=False,
                    order=440,
                    disable=True,
                )
            )

    for location in locations.locations:
        content = "\n\n".join(
            [
                f"Location: {location.name}",
                f"Type: {location.type}",
                "Sensory details:\n"
                + "\n".join(
                    f"- {sense}: {value}"
                    for sense, value in location.sensory_description.model_dump(exclude_none=True).items()
                ),
                "Notable features:\n" + "\n".join(f"- {item}" for item in location.notable_features),
                "Hidden elements:\n" + "\n".join(f"- {item}" for item in location.hidden_elements),
                f"NPCs present: {', '.join(location.npc_names) if location.npc_names else 'varies'}",
            ]
        )
        uid += 1
        add(
            _entry(
                uid,
                comment=f"Location: {location.name}",
                content=content,
                keys=_name_variants(location.name, type_hint=location.type),
                order=350,
            )
        )

    for clue in clue_graph.clues:
        rendered_targets = []
        for target in clue.points_to:
            value = plot.format_beat_reference(target.value) if target.type == "beat" else target.value
            rendered_targets.append(f"- {target.type}: {value}")
        content = "\n\n".join(
            [
                f"Clue {clue.id}",
                f"Found at: {clue.found_at_type} {clue.found_at}",
                f"Reveals: {clue.reveals}",
                "Points to:\n" + "\n".join(rendered_targets),
            ]
        )
        uid += 1
        add(
            _entry(
                uid,
                comment=f"Clue: {clue.id}",
                content=content,
                keys=[clue.found_at] if clue.found_at else [clue.id],
                order=300,
            )
        )

    branch_lines = [
        f"{branch.name}: if {branch.if_condition}, then {branch.then_outcome}. Consequences: {', '.join(branch.later_act_consequences)}"
        for branch in branches.branches
    ]
    branch_content = "\n\n".join(branch_lines)
    branch_keys: list[str] = []
    for branch in branches.branches:
        branch_keys.append(branch.name)
    uid += 1
    add(
        _entry(
            uid,
            comment="Branch Contingencies",
            content=branch_content,
            keys=branch_keys,
            order=700,
        )
    )

    if sample_characters is not None:
        sample_lines = [
            f"- {character.archetype}: {character.hook_into_campaign}"
            for character in sample_characters.characters
        ]
        sample_content = (
            "Pre-built sample characters available for this campaign. "
            "If a player needs help making a character, offer one of:\n\n"
            + "\n".join(sample_lines)
        )
        uid += 1
        add(
            _entry(
                uid,
                comment="Sample Characters",
                content=sample_content,
                keys=["sample characters", "pregens", "make a character", "character creation"],
                order=750,
            )
        )

    return {
        "name": title,
        "description": f"Campaign lorebook: {title} ({pack.metadata.display_name})",
        "entries": entries,
    }
