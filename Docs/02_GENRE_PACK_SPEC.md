# Genre Pack Specification

The contract every genre pack must satisfy. All tools (campaign generator, extension, pack generator) read packs according to this spec.

---

## Directory structure

A pack is a directory with a fixed file layout:

```
genres/<pack_name>/
├── pack.yaml                    # metadata and manifest
├── attributes.yaml              # the six attributes
├── resources.yaml               # resource mechanics (corruption, heat, etc.)
├── abilities.yaml               # ability categories and catalog
├── character_template.json      # starting character sheet shape
├── gm_prompt_overlay.md         # genre-specific GM prompt additions
├── tone.md                      # tone directives and thematic pillars
├── failure_moves.md             # genre-flavored GM moves
├── example_hooks.md             # 2-3 example opening scenes
├── generator_seed.yaml          # default seed for campaign generator
└── REVIEW_CHECKLIST.md          # generated with the pack; used for QA
```

All files must be present for a pack to validate.

---

## Who reads what

The pack is consumed by different systems, each reading only what it needs. Files left unread by a consumer are ignored — they're not wasted; they serve other consumers or humans.

| File | Campaign generator | Pack generator | Extension (browser) | GM (at runtime) |
|---|---|---|---|---|
| `pack.yaml` | ✅ metadata | ✅ writes | ✅ name + version | — |
| `attributes.yaml` | ✅ NPC & char creation | ✅ writes | ✅ dice + sheet UI | via overlay |
| `resources.yaml` | ✅ NPC consequences | ✅ writes | ✅ sheet state UI, STATUS_UPDATE whitelist, threshold logic | via overlay |
| `abilities.yaml` | ✅ NPC abilities | ✅ writes | ✅ ability catalog browser | via overlay |
| `character_template.json` | ✅ char creation guidance | ✅ writes | ✅ initialize new sheet | — |
| `gm_prompt_overlay.md` | ✅ tone calibration | ✅ writes | ❌ | ✅ embedded in lorebook |
| `tone.md` | ✅ hook style | ✅ writes | ❌ | ❌ |
| `failure_moves.md` | — | ✅ writes | ❌ | ✅ embedded in lorebook |
| `example_hooks.md` | ✅ hook calibration | ✅ writes | ❌ | ❌ |
| `generator_seed.yaml` | ✅ defaults | ✅ writes | ❌ | ❌ |
| `REVIEW_CHECKLIST.md` | ❌ | ✅ writes | ❌ | ❌ |

Key points:

- **The extension only reads 5 files** (`pack.yaml`, `attributes.yaml`, `resources.yaml`, `abilities.yaml`, `character_template.json`). Everything else is either for the Python tools, for humans, or reaches the GM via the campaign lorebook rather than through the extension.
- **The GM never reads pack files directly.** Pack content reaches the GM through (a) the `gm_prompt_overlay.md` embedded by the campaign generator as a constant lorebook entry, and (b) the attribute/resource/ability names that appear naturally in the character sheet injection (done by the extension) and in lorebook entries.
- **The campaign generator is the only consumer of tone/hooks reference files** (`tone.md`, `example_hooks.md`). These calibrate its own generation; they don't run at play time.
- **`failure_moves.md` reaches the GM** through the lorebook too — the campaign generator embeds its content as a constant lorebook entry alongside the GM overlay.

This separation is why the extension doesn't need a bundling step: it reads the pack directory directly via the browser's `webkitdirectory` file picker and pulls only the 5 files it needs. See `04_EXTENSION_BRIEF.md` § Pack loading for the mechanism.

---

## `pack.yaml`

Pack metadata. Example:

```yaml
schema_version: 1
pack_name: symbaroum_dark_fantasy
display_name: "Symbaroum Dark Fantasy"
version: 1.0.0
description: >
  Grim dark fantasy in the shadow of an ancient corrupting forest.
  Witches, inquisitors, and the price of forbidden knowledge.
inspirations: [symbaroum, witcher, dark_souls]
created: 2026-04-19
author: dudi
```

Required fields: `schema_version`, `pack_name`, `display_name`, `version`, `description`.

`schema_version` is currently `1`. Tools reject packs with unknown schema versions.

`pack_name` must be lowercase snake_case, used as the directory name and in CLI flags.

---

## `attributes.yaml`

Always exactly six attributes. The engine's dice math assumes six, and the UI renders six.

```yaml
attributes:
  - key: might
    display: Might
    description: Physical force, endurance, melee strength.
    examples: [smashing a locked door, wrestling a foe, enduring hardship]
  - key: finesse
    display: Finesse
    description: Agility, stealth, precision, reflexes.
    examples: [pickpocketing, dodging, striking a vital point]
  - key: wits
    display: Wits
    description: Reasoning, perception, recall of lore.
    examples: [solving a cipher, noticing a detail, recalling history]
  - key: will
    display: Will
    description: Resolve, mystic focus, resistance to corruption and mind-effects.
    examples: [resisting fear, channeling magic, staring down a demon]
  - key: presence
    display: Presence
    description: Persuasion, deception, command, social force.
    examples: [negotiation, intimidation, inspiring allies]
  - key: shadow
    display: Shadow
    description: Witchsight, occult intuition, corruption-touched actions.
    examples: [reading auras, sensing the unnatural, occult rituals]
```

Constraints:
- Exactly 6 entries. Tools reject packs with fewer or more.
- `key` must be lowercase snake_case; used in sheet JSON and dice commands.
- `display` is the human-facing name.
- `description` should be one sentence — used in the sheet UI tooltip and in the GM prompt overlay.
- `examples` is 2-4 short phrases helping the GM recognize when to call for this attribute.

The six keys MUST be unique. The six display names SHOULD be unique and memorable.

---

## `resources.yaml`

Resource mechanics that interact with the character sheet and GM moves.

```yaml
resources:
  - key: corruption_temporary
    display: Corruption (Temporary)
    kind: pool_with_threshold
    description: >
      Accumulates from using Shadow-based abilities, drinking from tainted sources,
      or making morally compromising choices. Resets to 0 on rest/ritual.
      When it reaches corruption_threshold, 1 permanent corruption is inflicted
      and temporary resets to 0.
    starting_value: 0
    decrement_triggers: [rest, cleansing_ritual]
    increment_triggers:
      - using a Shadow-tagged ability (1)
      - drinking from a tainted source (1)
      - morally compromising action (1-3 at GM discretion)

  - key: corruption_permanent
    display: Corruption (Permanent)
    kind: counter
    description: >
      Lifetime corruption accumulated. At high values (5+) the character
      physically changes; at the permanent threshold they become an
      NPC abomination (end of campaign).
    starting_value: 0
    threshold: 5
    threshold_effect: physical_transformation
    endgame_value: 10
    endgame_effect: npc_abomination

  - key: corruption_threshold
    display: Corruption Threshold
    kind: static_value
    description: >
      When corruption_temporary reaches this, 1 permanent corruption inflicted
      and temporary resets.
    starting_value: 5

  - key: hp_current
    display: Hit Points
    kind: pool
    description: Physical injury pool. At 0, character is dying.
    starting_value: 10
    max_value_field: hp_max

  - key: hp_max
    display: Max HP
    kind: static_value
    starting_value: 10
```

Constraints:
- At minimum, every pack declares `hp_current` and `hp_max`. These are engine-universal.
- Beyond that, the pack declares whatever resources fit the genre. Common patterns: single-resource-threshold (corruption), dual-track (sanity/stress), countdown (oxygen), heat (wanted level).
- `kind` must be one of: `pool`, `pool_with_threshold`, `counter`, `static_value`, `toggle`, `track`.
- The extension reads this file to know what fields to render in the sheet, which fields accept state deltas, and how to display them.
- STATUS_UPDATE blocks reference these keys directly.

---

## `abilities.yaml`

Ability categories and starter catalog.

```yaml
categories:
  - key: mystical_powers
    display: Mystical Powers
    description: >
      Active occult abilities. Using one requires a Will roll; failure
      inflicts 1 temporary corruption.
    activation: active
    roll_attribute: will
    consequence_on_failure: corruption_temporary +1
    consequence_on_partial: corruption_temporary +1 OR effect reduced
    has_levels: true
    level_names: [novice, adept, master]

  - key: abilities_general
    display: General Abilities
    description: Learned skills, martial training, professions.
    activation: passive_or_triggered
    has_levels: true
    level_names: [novice, adept, master]

  - key: rituals
    display: Rituals
    description: >
      Slow magic requiring time, components, and often a safe location.
      Not usable in combat.
    activation: ritual
    time_required: minutes_to_hours
    has_levels: false

  - key: traits
    display: Traits
    description: Permanent features of the character (racial, supernatural, etc.).
    activation: passive
    has_levels: false

catalog:
  - name: Witchsight
    category: mystical_powers
    prerequisite: shadow >= 1
    description: >
      Perceive the spiritual and corrupt nature of things and people.
      Auras, recent magic use, taint, presence of the unnatural.
    effect: >
      On successful Will roll, the GM reveals one significant spiritual
      truth about the target. On partial, reveals something but with
      ambiguity. On failure, reveals nothing and inflicts 1 corruption.

  - name: Shapeshifter
    category: mystical_powers
    prerequisite: shadow >= 2
    description: Assume the form of an animal you've studied.
    effect: >
      Will roll to transform. Duration: scene. Corruption on failure.
      Adept level: humanoid forms possible. Master: any animal.

  - name: Staff Fighting
    category: abilities_general
    prerequisite: none
    description: Trained use of quarterstaff as both weapon and walking stick.
    effect: >
      +1 to Might or Finesse rolls with a staff. Adept: parry bonus.
      Master: disarm on full success.

  # ... 15-25 more abilities spanning all categories
```

Constraints:
- At least 3 categories, at most 8.
- At least 15 abilities in the catalog, at least 2 per category.
- `prerequisite` can reference attributes (`shadow >= 1`), other abilities (`Witchsight`), or `none`.
- `consequence_on_failure` / `consequence_on_partial`: references resource keys from `resources.yaml`. Must validate.
- `activation` must be one of: `active`, `passive`, `triggered`, `passive_or_triggered`, `ritual`.
- The catalog is suggestive, not restrictive. Players and GMs can invent new abilities within a category; the catalog provides consistency and starting options.

---

## `character_template.json`

The starting shape of a character sheet. The extension reads this to know how to render the sheet UI and what state fields to track.

```json
{
  "name": "",
  "concept": "",
  "attributes": {
    "might": 0,
    "finesse": 0,
    "wits": 0,
    "will": 0,
    "presence": 0,
    "shadow": 0
  },
  "abilities": [
    { "name": "", "category": "", "level": null, "notes": "" }
  ],
  "equipment": [],
  "state": {
    "hp_current": 10,
    "hp_max": 10,
    "corruption_temporary": 0,
    "corruption_permanent": 0,
    "corruption_threshold": 5,
    "conditions": []
  },
  "notes": ""
}
```

Constraints:
- `attributes` object must have exactly the six keys from `attributes.yaml`.
- `state` object must include every `pool`, `pool_with_threshold`, `counter`, and `static_value` resource from `resources.yaml`.
- `abilities` is an array of objects; the shape is fixed (name, category, level, notes).
- `conditions` is an array of strings (free-form condition names the GM narrates).

Character creation uses this as the starting point; the player fills in values within the point-buy rules from `gm_prompt_overlay.md`.

---

## `gm_prompt_overlay.md`

Genre-specific additions to the base GM prompt. Concatenated after the engine prompt at chat creation.

Must include, in sections:

### Setting and tone

One paragraph establishing the setting's flavor. Not a plot — plot comes from the campaign. This is the ambient texture.

### Thematic pillars

3-5 thematic pillars that the GM should weave through scenes.

### Attribute guidance

Reminders for the GM about when to call on which attribute. Can cite the examples from `attributes.yaml`.

### Resource mechanics

How resources tick up and down. What corruption/sanity/heat/etc. feels like in play. When the GM should inflict them.

### Ability adjudication

For each category in `abilities.yaml`, a short paragraph on how the GM handles activations, costs, and consequences.

### Genre-specific NPC conventions

Archetypes that appear often (cultists, inquisitors, corrupt nobles, witch-hunters for fantasy; fixers, netrunners, corporate suits for cyberpunk). How they speak, what they want.

### Content to include / exclude

Explicit lists of themes the pack embraces and themes it avoids. This is both safety-conscious (you can exclude content you don't want to encounter) and tone-protecting (you can exclude content that doesn't fit the pack's mood).

### Character creation

Point-buy or array for attribute distribution. Number of starting abilities. Starting equipment guidance. Starting corruption/sanity/heat values.

The overlay must not override engine-level rules (resolution bands, STATUS_UPDATE format, OOC handling, etc.). Those are fixed.

---

## `tone.md`

Optional standalone tone document. Can repeat the tone sections from `gm_prompt_overlay.md` with more detail — used as reference material for pack authoring and not necessarily injected into every prompt. Can also include reference mood images, soundtrack suggestions, writing samples.

---

## `failure_moves.md`

Genre-flavored failure moves. The engine-level failure move list is universal; this document provides specific phrasings and consequences appropriate to the genre.

Example for Symbaroum:

```markdown
## On failure (2-6), the GM picks one:

- The shadows in the forest remember you now. Something watches from the dark.
- The corruption wells up — inflict 1 temporary corruption.
- A witch-hunter's horn sounds in the distance. They've caught your trail.
- The old magic recoils. An ally is caught in the backlash (injury, fear, condition).
- A truth about the dead surfaces, unwelcome.
- The thing you needed is no longer where it was, or is no longer what it was.
- [universal] Reveal an unwelcome truth or danger.
- [universal] Separate the character from something valued.
- [universal] Force a hard choice.
- [universal] Burn a resource (gear breaks, torch dies, spell slot consumed).
```

Mark `[universal]` entries that are genre-neutral fallbacks — these come from the engine and every pack inherits them.

---

## `example_hooks.md`

2-3 example opening hooks showing what the tone feels like at scene level. These are NOT used at runtime; they're reference material for the campaign generator (to calibrate its own hooks) and for pack authors (to verify the pack captures the intended feel).

---

## `generator_seed.yaml`

Default seed for the campaign generator when run against this pack. The user can override any field on the command line or in their own seed file.

```yaml
genre: symbaroum_dark_fantasy
setting_anchors: [deep_forest, ancient_ruins, forbidden_lore, witch_trials]
themes_include: [betrayal, legacy, the_cost_of_knowledge]
themes_exclude: [romance, child_endangerment]
tone: [grim, mysterious, morally_ambiguous]
num_acts: 4
num_npcs: 10
num_locations: 8
antagonist_archetypes_preferred: [corrupt_inquisitor, ancient_sorcerer, cult_leader]
```

---

## `REVIEW_CHECKLIST.md`

Generated alongside the pack. A markdown checklist for reviewing a newly-generated pack:

- [ ] Are the six attributes genuinely distinct? Do any two overlap?
- [ ] Is the tone section specific enough to steer the GM, but not so prescriptive that it forbids improvisation?
- [ ] Does the ability catalog have variety across categories, or is it lopsided?
- [ ] Do resource mechanics hook into both character sheet and GM moves?
- [ ] Does `gm_prompt_overlay.md` reference only attributes/resources/abilities that actually exist in the pack?
- [ ] Do the example hooks land the tone, or do they feel generic?
- [ ] Are the exclusion themes specific enough to matter?
- [ ] (More items added during pack generation based on what the LLM flags as uncertain.)

---

## Validation

Tools validate packs on load. Failing validation is a hard error, not a warning. Checks:

- All required files present
- `schema_version` supported
- `attributes.yaml` has exactly 6 entries with unique keys
- `character_template.json` `attributes` keys match `attributes.yaml` keys exactly
- `character_template.json` `state` includes every required resource from `resources.yaml`
- `abilities.yaml` categories referenced in `gm_prompt_overlay.md` all exist
- `abilities.yaml` catalog prerequisites reference real attributes or real ability names
- `resources.yaml` resources referenced by `abilities.yaml` all exist
- `generator_seed.yaml` `genre` field matches `pack.yaml` `pack_name`

The validator lives in the campaign generator's codebase (`campaign_generator/pack.py`) and is importable by the pack generator for post-generation validation.

---

## Forward compatibility

`schema_version` will be bumped when breaking changes are introduced. Each version number corresponds to a specific shape of this spec. Tools ship with migrations for older versions where feasible; when not feasible, the tool reports exactly which fields are new and suggests additions.

The spec is deliberately verbose and rigid because the cost of a loose spec here is cascading drift — the GM prompt references a field the extension doesn't know about, the campaign generator assumes an attribute that the pack renamed, and everything looks fine until session 3. Strict validation up front prevents this.
