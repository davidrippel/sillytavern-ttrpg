You are designing 3 ready-to-use sample player characters for a tabletop campaign that has already been fully generated. Each character must be presented in TWO shapes — a story-mode profile (description-only, no stats) and a pack-mode profile (genre-pack stats and abilities). Both shapes describe the SAME character.

# Inputs

You receive a JSON object with:

- `pack` — the genre pack metadata, including the canonical `attribute_keys`, the `attributes` list with `display` names and `description` text, the canonical `abilities` list, and the `character_template` showing the starting attribute/state shape
- `premise`, `plot` — the campaign premise and plot skeleton
- `factions`, `npcs`, `locations` — lists of canonical names from the campaign

# Goals

Produce exactly 3 sample characters that are:

1. **Archetypally distinct** — different temperaments, social standings, and approaches. Avoid duplicates.
2. **Plausibly hooked** into the campaign's premise, factions, NPCs, or locations. Each character's `hook_into_campaign` MUST mention at least one canonical faction, NPC, or location by name.
3. **Tonally consistent** with the genre pack and the campaign tone.
4. **Internally consistent** — the story-mode "good at"/"bad at" tags should reflect the same competencies the pack-mode attributes and abilities suggest.

# Schema constraints

For each character:

- `archetype`: a short label like "Disgraced scholar of the Order" or "Veteran free-blade".
- `hook_into_campaign`: 1 sentence connecting them to the campaign; reference at least one canonical name.
- `story.name`: the same name used in `pack.name`.
- `story.description`: 2-3 sentences of narrative description (who they are, what drives them).
- `story.strengths`: 1-2 short tag phrases (e.g., "quick with words", "knife-fighter", "reads people").
- `story.weakness`: 1 short tag phrase (e.g., "haunted by visions", "too proud to retreat").
- `pack.name`: same as `story.name`.
- `pack.concept`: a one-line concept ("disgraced scholar turned investigator").
- `pack.attributes`: an object whose keys are a subset of `pack.attribute_keys`. Values are integer modifiers in the −1..+2 range. Use ONLY keys from `attribute_keys`.
- `pack.abilities`: a list of ability names; every entry MUST appear in the `pack.abilities` input list.
- `pack.equipment`: 2-4 evocative items.
- `pack.notes`: 1-2 sentences of additional flavor (background, secret, or unfinished business).

Return strictly the JSON document for `SampleCharacterSet`.
