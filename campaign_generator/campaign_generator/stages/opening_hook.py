"""Compose the player-facing opening hook deterministically.

v1 / early-v2 used an LLM to write an "opening scene" paragraph and a
second LLM call to write a "what you already know" section. Both
routinely produced canon errors: the scene named strangers without
context (Marlowe before any introduction), swapped family roles
(Anya as the daughter when the roster says Chloe is), or invented
relationships that contradicted the NPC roster.

The current pipeline drops both LLM calls. Everything in the opening
hook is composed from canonical data we already have on disk:

  - premise, tone, hook         ← premise/plot stages
  - character-creation guidance ← deterministic from pack + premise
  - starting location           ← deterministic best-guess from the plot
  - known NPCs                  ← pc_known_npcs LLM vet (kept; one
                                  small structured call against a
                                  closed candidate set)
  - background facts            ← seed.protagonist_known_facts

There is no LLM call between the roster and the player's hook file;
role-swap and phantom-NPC failures are therefore structurally
impossible.

A couple of kwargs (``client``, ``system_prompt``, ``prior_knowledge_system_prompt``,
``model``, ``temperature``, ``validation_log``, ``progress_callback``)
are accepted for backward compatibility with callers; this module no
longer uses them and they may be omitted in new code.
"""
from __future__ import annotations

from collections.abc import Callable

from common.llm import LLMClient
from common.pack import GenrePack

from ..schemas import (
    KnownNPCEntry,
    LocationCatalog,
    NPCRoster,
    OpeningHookDocument,
    PlotSkeleton,
    PremiseDocument,
)
from ..seed import CampaignSeed
from ..validation import ValidationLog


# Kept as module attributes so older callers that pull
# ``opening_hook.PROMPT_FILE`` / ``opening_hook.PRIOR_KNOWLEDGE_PROMPT_FILE``
# don't blow up at import time. They are no longer read.
PROMPT_FILE = "09_opening_hook.md"
PRIOR_KNOWLEDGE_PROMPT_FILE = "09c_pc_known_npc_vet.md"

_USER_ALIASES = {"{{user}}", "user", "protagonist", "pc", "the protagonist", "the pc", "player"}


def _is_user_alias(name: str | None) -> bool:
    if not name:
        return False
    return name.strip().lower() in _USER_ALIASES


def _shorten(text: str, *, limit: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rsplit(" ", 1)[0].rstrip(".,;:") + "..."


def _character_guidance(
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    seed: CampaignSeed,
) -> list[str]:
    guidance = [
        f"Create someone built for this campaign's central pressure: {_shorten(premise.central_conflict)}",
        f"Give your character one personal reason to care about the opener: {_shorten(plot.hook)}",
        _pack_character_summary(pack),
    ]
    if seed.protagonist_archetype:
        guidance.insert(0, f"Best fit: {seed.protagonist_archetype}")
    return guidance


def _pack_character_summary(pack: GenrePack) -> str:
    return (
        f"Use the {pack.metadata.display_name} sheet: name + concept + 2–3 advantages "
        f"+ 1–2 disadvantages + a few belongings and relationships. Pick advantage and "
        f"disadvantage phrases from the pack reference (see `__pack_reference` in the "
        f"lorebook); make them specific and grounded in the genre."
    )


def _starting_location_sensory(
    locations: LocationCatalog | None,
    start_location_name: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(name, one-line-sensory)`` for the campaign's opening location.

    Falls back to ``(name, None)`` if the location isn't in the
    catalog, or ``(None, None)`` if there's no usable start location.
    """
    if not start_location_name or locations is None:
        return start_location_name, None
    for location in locations.locations:
        if location.name != start_location_name:
            continue
        senses = location.sensory_description
        # Prefer sight; fall back to whatever the location has.
        for candidate in (senses.sight, senses.sound, senses.smell):
            if candidate and candidate.strip():
                return location.name, _shorten(candidate.strip(), limit=220)
        return location.name, None
    return start_location_name, None


def _build_known_npcs(
    npcs: NPCRoster | None,
    known_npc_names: set[str] | None,
) -> list[KnownNPCEntry]:
    if not known_npc_names or npcs is None:
        return []
    out: list[KnownNPCEntry] = []
    for npc in npcs.npcs:
        if npc.name not in known_npc_names:
            continue
        relation = ""
        for rel in npc.relationships:
            if _is_user_alias(rel.name):
                relation = rel.description.strip()
                break
        out.append(KnownNPCEntry(name=npc.name, relation=relation))
    return out


def _build_meeting_now_npcs(
    npcs: NPCRoster | None,
    hook_text: str,
    known_npc_names: set[str] | None,
) -> list[KnownNPCEntry]:
    """NPCs named in the opening hook prose that aren't in the PC's
    pre-existing-knowledge set. The player reads the hook and sees
    these names without context — list them with their public-facing
    role so the document is self-contained.
    """
    if npcs is None or not hook_text:
        return []
    known = known_npc_names or set()
    out: list[KnownNPCEntry] = []
    seen: set[str] = set()
    for npc in npcs.npcs:
        if not npc.name or npc.name in known or npc.name in seen:
            continue
        # Match the NPC name as a whole word; case-sensitive on purpose
        # so common-word names like "Sun" don't false-positive on
        # sentence-initial prose.
        if npc.name not in hook_text:
            continue
        seen.add(npc.name)
        # Use the public role for context; fall back to a short slice of
        # physical_description if role is empty.
        relation = (npc.role or "").strip() or _shorten(npc.physical_description, limit=120)
        out.append(KnownNPCEntry(name=npc.name, relation=relation))
    return out


def render(
    pack: GenrePack,
    premise: PremiseDocument,
    plot: PlotSkeleton,
    seed: CampaignSeed,
    *,
    npcs: NPCRoster | None = None,
    locations: LocationCatalog | None = None,
    known_npc_names: set[str] | None = None,
    start_location_name: str | None = None,
    # Legacy kwargs — accepted for backward compatibility with the v1
    # caller signature but no longer used. See module docstring.
    client: LLMClient | None = None,
    system_prompt: str | None = None,
    prior_knowledge_system_prompt: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    validation_log: ValidationLog | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> OpeningHookDocument:
    del client, system_prompt, prior_knowledge_system_prompt, model, temperature  # noqa: F841
    del validation_log, progress_callback  # noqa: F841

    location_name, sensory = _starting_location_sensory(locations, start_location_name)
    known = _build_known_npcs(npcs, known_npc_names)
    meeting_now = _build_meeting_now_npcs(npcs, plot.hook or "", known_npc_names)
    background_facts = [
        str(fact).strip()
        for fact in (seed.protagonist_known_facts or [])
        if str(fact).strip()
    ]

    return OpeningHookDocument(
        premise=premise.premise_text,
        tone_statement=premise.tone_statement,
        character_creation_guidance=_character_guidance(pack, premise, plot, seed),
        starting_location=location_name,
        starting_location_sensory=sensory,
        starting_hook=_shorten(plot.hook or "", limit=600),
        known_npcs=known,
        meeting_now_npcs=meeting_now,
        background_facts=background_facts,
    )
