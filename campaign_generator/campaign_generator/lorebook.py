"""v2 lorebook assembly.

The campaign lorebook is the bundle of constant + keyword entries that
SillyTavern's World Info system loads alongside the chat. The v3
extension reads a small set of constant entries by exact ``comment``
to wire up its runtime:

  __pack_gm_overlay     ← embeds pack.gm_prompt_overlay
  __pack_complications  ← embeds pack.complications
  __pack_reference      ← embeds pack.advantages_disadvantages
                          plus a small JSON header used by the
                          compatibility check.
  __campaign_bible      ← premise / conflict / tone / thematic spine.
  __campaign_truths     ← JSON array of authored truths. Disabled so
                          the GM never sees the entry directly; the
                          extension reads it by comment lookup.
  __pack_initial_authors_note
                        ← turn-0 Author's Note seed. Disabled so the
                          GM never sees the entry directly; the
                          extension reads it by comment lookup on
                          campaign reset and writes it into the AN
                          slot.

Everything else (NPCs, locations, factions) is a normal keyword-
triggered entry. NPCs and locations also get a `(secret)` tier-2
companion entry that is `disabled: true` by default; the extension's
secrets.js unlocks them once the player has spent enough time on the
underlying entity.

The v1 node / clue / beat / current-act entries are gone.
"""
from __future__ import annotations

import json
import re
from typing import Any

from common.pack import GenrePack

from .schemas import (
    BranchPlan,
    ComplicationSet,
    FactionSet,
    LocationCatalog,
    NPCRoster,
    PlotSkeleton,
    PremiseDocument,
    SampleCharacterSet,
    TruthSet,
)


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


def _short_relationship_tag(description: str, *, max_len: int = 80) -> str:
    text = (description or "").strip()
    if not text:
        return ""
    for sep in (". ", "; ", " — ", ", "):
        idx = text.find(sep)
        if 0 < idx <= max_len:
            text = text[:idx]
            break
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text.rstrip(".").strip()


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
    exclude_recursion: bool = False,
    prevent_recursion: bool = False,
    match_whole_words: bool | None = None,
    scan_depth: int | None = None,
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
        "excludeRecursion": exclude_recursion,
        "preventRecursion": prevent_recursion,
        "delayUntilRecursion": 0,
        "probability": 100,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": scan_depth,
        "caseSensitive": None,
        "matchWholeWords": match_whole_words,
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
    truths: TruthSet,
    complications: ComplicationSet,
    branches: BranchPlan,
    sample_characters: SampleCharacterSet | None = None,
    initial_authors_note: str | None = None,
) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    uid = 0

    def add(entry: dict[str, Any]) -> None:
        entries[str(entry["uid"])] = entry

    # ---- Constant tier — the four `__pack_*` + `__campaign_*` entries
    # the v3 extension binds to by exact comment.

    uid += 1
    add(_entry(
        uid,
        comment="__pack_gm_overlay",
        content=pack.gm_prompt_overlay,
        constant=True,
        order=1000,
    ))

    uid += 1
    add(_entry(
        uid,
        comment="__pack_complications",
        content=_compose_complications_text(pack.complications, complications),
        constant=True,
        order=950,
    ))

    uid += 1
    add(_entry(
        uid,
        comment="__pack_reference",
        content=_compose_pack_reference(pack),
        constant=True,
        order=940,
    ))

    title = (premise.title or pack.metadata.display_name).strip()
    uid += 1
    add(_entry(
        uid,
        comment="__campaign_bible",
        content=_compose_campaign_bible(premise, plot, title),
        constant=True,
        order=900,
    ))

    # __campaign_truths is intentionally `disable: true` — the GM never
    # sees it via keyword firing. The extension reads it by comment
    # lookup and injects one truth at a time as a director's note.
    uid += 1
    add(_entry(
        uid,
        comment="__campaign_truths",
        content=json.dumps(
            [t.model_dump() for t in truths.truths],
            ensure_ascii=False,
            indent=2,
        ),
        constant=False,
        disable=True,
        order=0,
    ))

    # __pack_initial_authors_note is the turn-0 AN seed. The extension's
    # "Reset campaign" button reads this by comment lookup and writes it
    # straight into the Author's Note slot. Disabled so the GM never
    # sees it via keyword firing.
    if initial_authors_note:
        uid += 1
        add(_entry(
            uid,
            comment="__pack_initial_authors_note",
            content=initial_authors_note,
            constant=False,
            disable=True,
            order=0,
        ))

    # ---- Faction tier --------------------------------------------------

    for faction in factions.factions:
        uid += 1
        keys = _name_variants(faction.name)
        add(_entry(
            uid,
            comment=f"Faction: {faction.name}",
            content=_compose_faction(faction),
            keys=keys,
            order=500,
            prevent_recursion=True,
            scan_depth=25,
        ))

    # ---- NPC tier (public + secret) -----------------------------------

    for npc in npcs.npcs:
        uid += 1
        public_keys = _name_variants(npc.name)
        add(_entry(
            uid,
            comment=f"NPC: {npc.name}",
            content=_compose_npc_public(npc),
            keys=public_keys,
            order=450,
            prevent_recursion=True,
            scan_depth=25,
        ))
        # Secret companion entry (tier-2): disabled by default; the
        # extension's secrets.js enables it when the player has
        # accumulated enough facts/threads naming this NPC.
        if npc.secret:
            uid += 1
            add(_entry(
                uid,
                comment=f"NPC Secret: {npc.name}",
                content=_compose_npc_secret(npc),
                keys=public_keys,
                order=440,
                disable=True,
                prevent_recursion=True,
                scan_depth=10,
            ))

    # ---- Location tier (public + secret) ------------------------------

    for location in locations.locations:
        uid += 1
        public_keys = _name_variants(location.name, type_hint=location.type)
        add(_entry(
            uid,
            comment=f"Location: {location.name}",
            content=_compose_location_public(location),
            keys=public_keys,
            order=350,
            prevent_recursion=True,
            scan_depth=25,
        ))
        if location.hidden_elements:
            uid += 1
            add(_entry(
                uid,
                comment=f"Location Secret: {location.name}",
                content=_compose_location_secret(location),
                keys=public_keys,
                order=340,
                disable=True,
                prevent_recursion=True,
                scan_depth=10,
            ))

    # ---- Branches (informational) -------------------------------------

    if branches.branches:
        uid += 1
        add(_entry(
            uid,
            comment="Branch Contingencies",
            content=_compose_branches(branches),
            keys=[],
            constant=False,
            order=700,
            disable=True,  # GM-facing reference; enable manually if desired
        ))

    # ---- Sample characters (informational) ----------------------------

    if sample_characters is not None and sample_characters.characters:
        uid += 1
        add(_entry(
            uid,
            comment="Sample Characters",
            content=_compose_sample_characters(sample_characters),
            keys=[],
            constant=False,
            order=750,
            disable=True,
        ))

    return {"entries": entries}


# ---- Content composition ------------------------------------------------


def _compose_pack_reference(pack: GenrePack) -> str:
    header = {
        "pack_name": pack.metadata.pack_name,
        "pack_version": pack.metadata.version,
        "display_name": pack.metadata.display_name,
    }
    return (
        json.dumps(header, ensure_ascii=False, indent=2)
        + "\n\n"
        + pack.advantages_disadvantages
    )


def _compose_complications_text(pack_complications: str, campaign_complications: ComplicationSet) -> str:
    pack_block = pack_complications.strip() if pack_complications else ""
    campaign_lines = ["## Campaign-specific complications", ""]
    for entry in campaign_complications.complications:
        campaign_lines.append(f"- **{entry.title}** {entry.body}")
    parts = []
    if pack_block:
        parts.append(pack_block)
    parts.append("\n".join(campaign_lines).rstrip())
    return "\n\n".join(parts)


def _compose_campaign_bible(premise: PremiseDocument, plot: PlotSkeleton, title: str) -> str:
    return "\n\n".join([
        f"Title: {title}",
        premise.premise_text,
        f"Central conflict: {premise.central_conflict}",
        f"Tone: {premise.tone_statement}",
        "Thematic pillars:\n" + "\n".join(f"- {p}" for p in premise.thematic_pillars),
        "Thematic spine (escalation themes):\n" + "\n".join(f"- {s}" for s in plot.thematic_spine),
        f"Driving mystery: {plot.driving_mystery}",
        f"Hook: {plot.hook}",
        f"Escalation arc: {plot.escalation_arc}",
        (
            "Antagonist: "
            + plot.main_antagonist.name
            + " — "
            + plot.main_antagonist.motivation
            + " (relationship to protagonist: "
            + plot.main_antagonist.relationship_to_protagonist
            + ")"
        ),
    ])


def _compose_faction(faction) -> str:
    return "\n\n".join([
        f"{faction.name} ({faction.moral_alignment})",
        faction.description,
        "Goals:\n" + "\n".join(f"- {g}" for g in faction.goals),
        "Methods:\n" + "\n".join(f"- {m}" for m in faction.methods),
        "Internal tensions:\n" + "\n".join(f"- {t}" for t in faction.internal_tensions),
        f"Relationship to the plot: {faction.relationship_to_plot}",
    ])


def _compose_npc_public(npc) -> str:
    lines = [
        f"{npc.name} — {npc.role}",
        f"Affiliation: {npc.faction_affiliation or 'independent'}",
        f"Appearance: {npc.physical_description}",
        f"Speech: {npc.speaking_style}",
        f"Motivation: {npc.motivation}",
    ]
    if npc.advantages:
        lines.append("Advantages: " + "; ".join(npc.advantages))
    if npc.relationships:
        rels = []
        for rel in npc.relationships:
            tag = _short_relationship_tag(rel.description)
            rels.append(f"{rel.name} — {tag}" if tag else rel.name)
        lines.append("Relationships: " + "; ".join(rels))
    if npc.discovery_surfaces:
        lines.append(
            "Discovery surfaces:\n" + "\n".join(f"- {h}" for h in npc.discovery_surfaces)
        )
    return "\n".join(lines)


def _compose_npc_secret(npc) -> str:
    return (
        f"SECRET about {npc.name} — reveal-eligible only when the player has "
        f"earned proximity:\n\n{npc.secret}"
    )


def _compose_location_public(location) -> str:
    senses = []
    if location.sensory_description.sight:
        senses.append(f"Sight: {location.sensory_description.sight}")
    if location.sensory_description.sound:
        senses.append(f"Sound: {location.sensory_description.sound}")
    if location.sensory_description.smell:
        senses.append(f"Smell: {location.sensory_description.smell}")
    lines = [
        f"{location.name} ({location.type})",
        "\n".join(senses),
        "Notable features:\n" + "\n".join(f"- {f}" for f in location.notable_features),
    ]
    if location.npc_names:
        lines.append("Found here: " + ", ".join(location.npc_names))
    if location.discovery_surfaces:
        lines.append(
            "Discovery surfaces:\n" + "\n".join(f"- {h}" for h in location.discovery_surfaces)
        )
    return "\n\n".join(lines)


def _compose_location_secret(location) -> str:
    return (
        f"HIDDEN at {location.name} — reveal-eligible only when the player "
        f"has earned proximity:\n\n"
        + "\n".join(f"- {h}" for h in location.hidden_elements)
    )


def _compose_branches(branches: BranchPlan) -> str:
    lines = ["## Branch contingencies", ""]
    for branch in branches.branches:
        lines.append(f"### {branch.name}")
        lines.append(f"IF: {branch.if_condition}")
        lines.append(f"THEN: {branch.then_outcome}")
        if branch.later_consequences:
            lines.append("Later: " + "; ".join(branch.later_consequences))
        if branch.references:
            lines.append("References: " + ", ".join(branch.references))
        lines.append("")
    return "\n".join(lines).rstrip()


def _compose_sample_characters(sample_characters: SampleCharacterSet) -> str:
    lines = ["## Sample characters (story-mode)", ""]
    for character in sample_characters.characters:
        lines.append(f"### {character.name}")
        lines.append(character.concept)
        lines.append("Advantages: " + "; ".join(character.advantages))
        lines.append("Disadvantages: " + "; ".join(character.disadvantages))
        if character.belongings:
            lines.append("Belongings: " + ", ".join(character.belongings))
        if character.relationships:
            rels = [f"{r.name} ({r.tie})" for r in character.relationships]
            lines.append("Relationships: " + "; ".join(rels))
        lines.append(f"Hook: {character.hook_into_campaign}")
        lines.append("")
    return "\n".join(lines).rstrip()
