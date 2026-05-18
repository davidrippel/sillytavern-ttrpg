# Genre Pack Specification

The contract every genre pack must satisfy. All tools (campaign generator, extension, pack generator) read packs according to this spec.

This is the **schema v2** spec. Schema v2 is story-mode only — no attribute scores, no resource pools, no dice. Earlier versions of this system supported stat-mode packs with `attributes.yaml`, `resources.yaml`, and `abilities.yaml`; those files are retired and tools reject packs that contain them under the v2 schema.

---

## Directory structure

A pack is a directory with a fixed file layout:

```
genres/<pack_name>/
├── pack.yaml                       # metadata
├── character_template.json         # starting character sheet shape
├── gm_prompt_overlay.md            # genre-specific GM prompt additions
├── tone.md                         # tone directives and thematic pillars
├── complications.md                # genre-flavored narrative complications
├── advantages_disadvantages.md     # vocabulary of strengths and weaknesses
├── example_hooks.md                # 2-3 example opening scenes
├── generator_seed.yaml             # default seed for campaign generator
├── naming.yaml                     # optional — naming-diversity hints
└── REVIEW_CHECKLIST.md             # generated with the pack; used for QA
```

All files must be present for a pack to validate, except `naming.yaml`, which is optional.

---

## Who reads what

| File | Campaign generator | Pack generator | Extension (browser) | GM (at runtime) |
|---|---|---|---|---|
| `pack.yaml` | ✅ metadata | ✅ writes | ✅ name + version | — |
| `character_template.json` | ✅ char creation guidance | ✅ writes | ✅ initialize new sheet | — |
| `gm_prompt_overlay.md` | ✅ tone calibration | ✅ writes | ❌ | ✅ embedded in lorebook (`__pack_gm_overlay`) |
| `tone.md` | ✅ hook style | ✅ writes | ❌ | ❌ |
| `complications.md` | ✅ pacing/complication seed | ✅ writes | ❌ | ✅ embedded in lorebook (`__pack_complications`) |
| `advantages_disadvantages.md` | ✅ sample-character vocab | ✅ writes | ✅ sheet UI autocomplete | ✅ embedded in lorebook (`__pack_reference`) |
| `example_hooks.md` | ✅ hook calibration | ✅ writes | ❌ | ❌ |
| `generator_seed.yaml` | ✅ defaults | ✅ writes | ❌ | ❌ |
| `naming.yaml` | ✅ NPC/location naming diversity | ✅ writes | ❌ | ❌ |
| `REVIEW_CHECKLIST.md` | ❌ | ✅ writes | ❌ | ❌ |

Key points:

- **The extension reads only 3 files** (`pack.yaml`, `character_template.json`, `advantages_disadvantages.md`). Everything else is either for the Python tools, for humans, or reaches the GM via the campaign lorebook.
- **The GM never reads pack files directly.** Pack content reaches the GM through three constant lorebook entries the campaign generator embeds:
  - `__pack_gm_overlay` — full text of `gm_prompt_overlay.md`
  - `__pack_complications` — full text of `complications.md`
  - `__pack_reference` — full text of `advantages_disadvantages.md`
- **The campaign generator is the only consumer of tone/hooks reference files** (`tone.md`, `example_hooks.md`). These calibrate its own generation; they don't run at play time.

---

## `pack.yaml`

Pack metadata. Example:

```yaml
schema_version: 2
pack_name: symbaroum_dark_fantasy
display_name: "Symbaroum Dark Fantasy"
version: 2.0.0
description: >
  Grim dark fantasy in the shadow of an ancient corrupting forest.
inspirations: [symbaroum, witcher, dark_souls]
created: 2026-04-19
updated: 2026-05-16
author: dudi
```

Required fields: `schema_version`, `pack_name`, `display_name`, `version`, `description`.

`schema_version` must be `2`. Tools reject packs with `schema_version: 1` and instruct the user to migrate (or regenerate).

`pack_name` must be lowercase snake_case, used as the directory name and in CLI flags.

---

## `character_template.json`

The starting shape of a story-mode character sheet. The extension reads this to initialize a new sheet and render the UI.

```json
{
  "name": "",
  "concept": "",
  "advantages": [],
  "disadvantages": [],
  "belongings": [],
  "relationships": [],
  "notes": ""
}
```

Field meanings:

- `name`: free string.
- `concept`: 1–2 sentence summary of who the character is and what drew them into the story.
- `advantages`: array of short strings (typical: 2–3). Concrete strengths the GM can recognize and lean on. *"Trained witchsight"* lands; *"strong"* does not.
- `disadvantages`: array of short strings (typical: 1–2). Concrete weaknesses, marks, debts, or vulnerabilities the world can exploit.
- `belongings`: array of short strings (typical: 3–5). Notable items beyond travel basics — relics, named weapons, letters, charms.
- `relationships`: array of objects `{ "name": "...", "tie": "..." }`. Named NPCs the character is tied to.
- `notes`: free-form string for the player's own jotting (private from the GM).

Constraints (validated):

- All keys present, even if value is `""` or `[]`.
- `advantages` and `disadvantages` are arrays of strings.
- `relationships` entries (when present) have both `name` and `tie`.
- No legacy keys (`attributes`, `abilities`, `state`, `equipment`). The validator rejects packs that include them — convert to `belongings` and the new fields, don't keep both.

The pack may seed default belongings or canonical advantages/disadvantages in this file (a witch-hunter pack might pre-fill `belongings: ["silver-edged knife", "manual of rites"]`); the character creation flow in the extension takes the file as a starting point and lets the player edit any field.

---

## `gm_prompt_overlay.md`

Genre-specific additions to the base GM prompt. Reaches the GM as a constant lorebook entry (`__pack_gm_overlay`).

Required sections (in this order):

### Setting and tone

One paragraph establishing the setting's flavor. Not a plot — plot comes from the campaign. This is the ambient texture.

### Thematic pillars

3–5 thematic pillars the GM should weave through scenes. One sentence each.

### Resolving actions — narrative, no dice

How the GM adjudicates without rolls in this genre. Must cover:

- What it feels like when an advantage is in play and the situation is favorable (lean toward success-with-cost; what kinds of costs fit this genre).
- What it feels like when a disadvantage is in play or the situation is hostile (lean toward failure or partial success; reference `__pack_complications`).
- The default for neutral cases.

Reference the genre's `advantages_disadvantages.md` vocabulary so the GM knows the kinds of phrases to recognize.

### Translating mechanical pressures into fiction

The genre's signature pressures (corruption, heat, sanity, ship damage, exposure, etc.) rendered as accumulating narrative weight rather than counters. For each pressure:

- The concrete sensory or social signs the GM can name in prose.
- When to escalate from accumulating signs to a permanent change (a scar, a mark, a debt, a reputation shift).

The fact extractor picks these up from prose. The GM does not track numbers.

### NPC conventions

3–6 archetypes the genre commonly features (inquisitors, witches, fixers, netrunners, corp suits). For each: how they speak, what they want, default disposition toward the protagonist.

### Content to include / Content to avoid

Two explicit lists. Genre-embracing themes and genre-incompatible or unwanted themes. Used by the campaign generator's content filters and by the GM at play time.

### Character creation

Concrete guidance on how a character in this genre is built using the `character_template.json` shape. How many advantages and disadvantages, what kinds of belongings fit, how many relationships to seed. Starting marks of the genre (already-corrupted starting character? already-wanted? already-bonded?).

The overlay must not override engine-level rules in the base GM prompt (NPC format, OOC handling, length cap, "never invent campaign truths"). Those are fixed.

Aim for under 1500 words total.

---

## `complications.md`

Genre-flavored narrative complications. Reaches the GM as a constant lorebook entry (`__pack_complications`).

No roll bands, no numbers. Each complication is a concrete narrative consequence the GM can pick when an action goes badly or when a "lean in" pacing cue arrives. Aim for 10–15 genre-specific complications plus 5–8 universal ones (marked `[universal]`).

Example format:

```markdown
## <Genre> complications

- **The shadows in the forest remember.** Something watches from the dark. ...
- **The Church takes notice.** An inquisitor, a report, a visit from a priest. ...
- ...

## When the action succeeds but the world still pushes back

- Success, but it takes much longer than hoped.
- Success, but you leave a trail — someone can follow.
- ...
```

Good complications:

- Are *specific* to the genre (not "something bad happens").
- Are *actionable* (describe a concrete change to the situation).
- Ratchet tension rather than ending scenes.
- Can be combined with the genre's accumulating pressures (e.g. a corruption sign appears alongside the complication).

The "success but..." section is mandatory in v2 — clean wins should be rare across most genres, and the GM needs a vocabulary of soft costs.

---

## `advantages_disadvantages.md`

The genre's vocabulary of strengths and weaknesses. Reaches the GM as a constant lorebook entry (`__pack_reference`), reaches the extension's character-sheet UI as autocomplete suggestions, reaches the campaign generator as raw material for sample characters.

Two parts:

### Advantages

Organized by axis (bodily / knowledge / social / mystical or genre-specific axes). For each axis, 4–8 example phrases. Phrases are:

- **Specific.** *"Trained witchsight"* not *"good at magic."*
- **Invocable.** The player can point at one and say "this is in play right now."
- **Genre-grounded.** No mechanical jargon. No cross-genre items.

### Disadvantages

Same shape. Aim for axes like "marked / wounded / bound / hunted."

The list is illustrative, not prescriptive. Players invent their own; the campaign generator may invent NPC advantages within these conventions. The list's job is to establish the *shape* of valid entries.

---

## `tone.md`

Optional standalone tone document. Mood notes, soundtrack, writing sample, visual references. Used as reference material for pack authoring and for the campaign generator's prose calibration — not injected into the GM's prompt.

Can be empty. Don't pad.

---

## `example_hooks.md`

2–3 example opening hooks showing what the tone feels like at scene level. 2–3 paragraphs each, ending at a moment of choice. NOT used at runtime; reference material for the campaign generator (to calibrate hook generation) and for pack authors (to verify the pack captures the intended feel).

---

## `generator_seed.yaml`

Default seed for the campaign generator when run against this pack. The user can override any field on the command line or in their own seed file.

```yaml
genre: symbaroum_dark_fantasy
setting_anchors: [deep_forest, ancient_ruins, forbidden_lore, witch_trials]
themes_include: [betrayal, legacy, the_cost_of_knowledge]
themes_exclude: [romance, child_endangerment]
tone: [grim, mysterious, morally_ambiguous]
num_npcs: 18
num_locations: 12
num_factions: 4
num_truths: 7
num_complications: 12
antagonist_archetypes_preferred:
  - corrupt_inquisitor
  - ancient_sorcerer
  - cult_leader
```

Fields:

- `num_truths`: how many atomic campaign truths the generator's truths stage should produce (typical: 5–10).
- `num_complications`: how many campaign-specific complications the generator should layer on top of the pack's universal complications (typical: 8–15).
- Removed in v2: `clue_chain_density`, `branch_points`, `num_acts`. The campaign no longer has acts, beats, or clue chains.

---

## `naming.yaml` (optional)

Naming-diversity hints consumed by the campaign generator's NPC and location stages. Both lists are optional; the generator falls back to genre-agnostic defaults when a list is empty or the file is absent.

```yaml
naming_registers:
  - "post-Earth creole drift — recognizable Earth roots fused or vowel-shifted across generations (Yuko-Ade, Marisol-7, Jaq, Nnedi-Vance)"
  - "..."
district_flavors:
  - "habitation-ring deck levels — gravity falls off the higher you live, and so does respectability"
  - "..."
```

Per run, the campaign generator picks one primary and one secondary `naming_registers` entry plus one `district_flavors` entry (sampled from the seed's `random_seed`) and injects them into the NPC and location prompts. Aim for 8–14 registers and 8–16 district flavors.

Style:

- Each entry is a one-sentence description specific enough that an LLM, given just that sentence, can sample plausible names or imagine the location archetype.
- Cover the genre's social spectrum.
- For invented-culture registers, describe the *pattern* (compound construction, honorific particles, generational markers), not just vibes.

---

## `REVIEW_CHECKLIST.md`

Generated alongside the pack. A markdown checklist with items specific to this pack that a reviewer should walk through. Typical sections: tone, adjudication without dice, truths and reveals, content safety, playtest items, pack-generator items.

---

## Validation

Tools validate packs on load. Failing validation is a hard error. Checks:

- All required files present
- `pack.yaml` `schema_version` is `2`
- No legacy files present (`attributes.yaml`, `resources.yaml`, `abilities.yaml`, `failure_moves.md`)
- `character_template.json` contains exactly the v2 keys; no legacy keys
- `gm_prompt_overlay.md` references the `__pack_complications` and `__pack_reference` lorebook entries by name (the generator embeds them; the overlay should point the GM at them)
- `gm_prompt_overlay.md` contains every required section header
- `generator_seed.yaml` `genre` matches `pack.yaml` `pack_name`
- `generator_seed.yaml` does not contain retired fields (`clue_chain_density`, `branch_points`, `num_acts`)

The validator lives in the campaign generator's codebase (`campaign_generator/pack.py`) and is importable by the pack generator for post-generation validation.

---

## Migrating a v1 pack to v2

A v1 pack (stat-mode with attributes/resources/abilities) is not auto-migrated. The retirement is intentional: the v2 grammar is different enough that mechanical translation produces unplayable packs. Hand-migrate:

1. Delete `attributes.yaml`, `resources.yaml`, `abilities.yaml`, `failure_moves.md`.
2. Rewrite `character_template.json` to the v2 shape — translate the character's stats into 2–3 advantages, the character's weaknesses into 1–2 disadvantages, the character's notable gear into `belongings`, and any NPC ties into `relationships`.
3. Rewrite `gm_prompt_overlay.md`: drop the *resource mechanics* and *ability adjudication* sections; replace with the new *resolving actions* and *translating mechanical pressures* sections. The pack's mechanical levers (corruption, heat, sanity) become accumulating narrative signs.
4. Convert `failure_moves.md` to `complications.md`. Drop the "(2-6)" / "(7-9)" band labels — complications are now picked by GM judgement of fiction, not roll bands. Add the "success but..." section.
5. Author `advantages_disadvantages.md` from scratch — there is no v1 equivalent.
6. Update `generator_seed.yaml`: drop `clue_chain_density`, `branch_points`, `num_acts`; add `num_truths`, `num_complications`, `num_factions`.
7. Bump `pack.yaml` `schema_version` to `2` and `version` to a major bump.

---

## Forward compatibility

`schema_version` will be bumped when breaking changes are introduced. Each version corresponds to a specific shape of this spec. Tools ship with migrations where feasible; when not feasible, the tool reports exactly which fields changed and suggests next steps.

The spec is deliberately rigid because the cost of a loose spec is cascading drift — the GM prompt references a section the extension doesn't know about, the campaign generator assumes a field the pack renamed. Strict validation up front prevents this.
