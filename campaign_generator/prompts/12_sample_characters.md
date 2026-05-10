You are designing ready-to-use sample player characters for a tabletop campaign that has already been fully generated. Each character must be presented in TWO shapes — a story-mode profile (description-only, no stats) and a pack-mode profile (genre-pack stats and abilities). Both shapes describe the SAME character.

# Inputs

You receive a JSON object with:

- `pack` — the genre pack metadata, including the canonical `attribute_keys`, the `attributes` list with `display` names and `description` text, the canonical `abilities` list, and the `character_template` showing the starting attribute/state shape
- `num_sample_characters` — the exact number of characters to produce
- `protagonist` — constraints the pregens MUST satisfy:
  - `archetype` (string or null): the protagonist's role/situation (e.g., age, profession, life situation). When present, every character is a plausible portrayal of this same protagonist.
  - `known_facts` (array of strings): facts about the protagonist that every character must be consistent with.
- `premise`, `plot` — the campaign premise and plot skeleton
- `factions`, `npcs`, `locations` — lists of canonical names from the campaign. The `npcs` list has been pre-filtered to only those the protagonist plausibly knows at the start of the story; do not invent or reference other NPCs.

# Goals

Produce exactly `num_sample_characters` sample characters that are:

1. **Faithful to the protagonist** — when `protagonist.archetype` is provided, every character must be a plausible variant of that protagonist (same age range, gender, life situation, etc.). Every entry in `protagonist.known_facts` must hold true for each character. Do not contradict the premise's framing of the protagonist.
2. **Archetypally distinct** — different temperaments, social standings, and approaches within the protagonist constraints. Avoid duplicates.
3. **Plausibly hooked** into the campaign's premise, factions, NPCs, or locations. Each character's `hook_into_campaign` MUST mention at least one canonical name from the provided `factions`, `npcs`, or `locations` lists. Do NOT reference any NPC not present in the input list — those are characters the protagonist would not yet know.
4. **Tonally consistent** with the genre pack and the campaign tone.
5. **Internally consistent** — the story-mode "good at"/"bad at" tags should reflect the same competencies the pack-mode attributes and abilities suggest.

# Schema constraints

For each character:

- `archetype`: a short label like "Disgraced scholar of the Order" or "Veteran free-blade".
- `hook_into_campaign`: 1 sentence connecting them to the campaign; reference at least one canonical name from the provided lists.
- `story.name`: the same name used in `pack.name`.
- `story.description`: 2-3 sentences of narrative description (who they are, what drives them).
- `story.strengths`: 1-2 short tag phrases (e.g., "quick with words", "knife-fighter", "reads people").
- `story.weakness`: 1 short tag phrase (e.g., "haunted by visions", "too proud to retreat").
- `pack.name`: same as `story.name`.
- `pack.concept`: a one-line concept ("disgraced scholar turned investigator").
- `pack.attributes`: an object whose keys are a subset of `pack.attribute_keys`. Values are integer modifiers in the −1..+2 range. Use ONLY keys from `attribute_keys`.
- `pack.abilities`: a list of ability names; every entry MUST appear verbatim in the input `pack.abilities` list. Do NOT invent abilities. Do NOT use attribute keys (e.g. "Stamina", "Charm") as abilities — attributes and abilities are disjoint catalogs.
- `pack.equipment`: 2-4 evocative items.
- `pack.notes`: 1-2 sentences of additional flavor (background, secret, or unfinished business).

Return strictly the JSON document for `SampleCharacterSet`.
