# Pack Generator — Claude Code Brief

Build a Python tool that generates a complete, validated genre pack from a short human-written brief. This is a separate tool from the campaign generator but shares some infrastructure.

Hand this file to Claude Code along with `01_SYSTEM_OVERVIEW.md`, `02_GENRE_PACK_SPEC.md`, and `06_PACK_AUTHORING_GUIDE.md` for context.

---

## Goal

Given a short high-level genre brief, produce a full genre pack directory that validates against `02_GENRE_PACK_SPEC.md`. The output is a first draft intended for human review and refinement — the `REVIEW_CHECKLIST.md` it produces alongside the pack guides that review.

Input: a genre brief YAML (small, human-written, see below).

Output: a complete pack directory with all files required by the spec, plus the review checklist.

**No bundling step.** The output is a directory of individual files, as specified in `02_GENRE_PACK_SPEC.md`. Python tools (campaign generator) read the directory directly. The SillyTavern extension reads the directory via its browser directory picker (see `04_EXTENSION_BRIEF.md` § Pack loading). There is no `pack.json` bundle; there is no import step; the pack is always the directory on disk.

---

## Tech stack

Same as the campaign generator:
- Python 3.11+, httpx, pydantic v2, pyyaml, typer, tenacity, rich, pytest
- OpenRouter API, default `anthropic/claude-sonnet-4.5`
- Importable code from the campaign generator where reasonable — specifically, `campaign_generator/pack.py` (validation) and `campaign_generator/llm.py` (LLM client)

Recommended: ship both tools in one repo or monorepo. The shared modules go in a `common/` package both tools depend on.

---

## CLI interface

```
python -m pack_generator \
    --brief my_genre_brief.yaml \
    --output genres/space_opera_adventure/ \
    --model anthropic/claude-sonnet-4.5
```

Flags:
- `--brief PATH` (required) — genre brief YAML
- `--output PATH` (required) — pack directory to create (must not exist or be empty)
- `--model STR` — OpenRouter model slug
- `--stages STR` — `all` or comma-separated list
- `--dry-run` — use cheap model

---

## Genre brief format

The brief is deliberately small. The user writes 15-40 lines; the generator fills in the rest via the pipeline.

```yaml
pack_name: space_opera_adventure
display_name: "Space Opera Adventure"
schema_version: 1

one_line_pitch: >
  Smugglers, derelict colonies, and ancient alien tech on the frontier
  of known space. Think Firefly meets Alien.

tone_keywords: [gritty, hopeful, wondrous, dangerous, blue-collar]

thematic_pillars_hint: >
  Community under pressure. The cost of freedom. What the old ones left
  behind. Generate 3-5 pillars in this vein.

content_to_avoid: [military_jingoism, grimdark_nihilism, racial_essentialism]

attribute_flavor: >
  Six attributes covering physical, mental, social, and tech/skill capabilities.
  Lean into the genre: piloting and mechanical intuition matter, as does
  social navigation in a multicultural frontier. Use names that feel
  space-opera, not generic fantasy.

resource_flavor: >
  One primary resource representing long-term wear — could be ship condition,
  fuel, or crew morale, whichever best captures the genre's stakes.
  One short-term resource representing immediate pressure — heat (wanted
  level), oxygen, or adrenaline. Pick what fits the one-line pitch best.

ability_categories_hint: >
  Include piloting/navigation, combat/small arms, ship systems/mechanics,
  and at least one "weird" category — psionics, alien tech, or
  something genre-defining. Decide on the final set.

example_inspiration_list: >
  Firefly, Alien, The Expanse, early Star Wars (pre-prequel), Outer Wilds.

example_characters: >
  A smuggler-captain with a haunted past. A xenoarcheologist who's seen
  too much. A mechanic who talks to ships. An ex-corporate-security
  trying to disappear. Use these as a vibe check for ability catalog
  and tone.

campaign_style_hint: >
  Episodic adventures with an overarching mystery. Ships as homes.
  Strangers on the same ship eventually become family (or kill each other).
```

Required fields: `pack_name`, `display_name`, `schema_version`, `one_line_pitch`, `tone_keywords`, `attribute_flavor`, `resource_flavor`, `ability_categories_hint`.

Optional but recommended: `thematic_pillars_hint`, `content_to_avoid`, `example_inspiration_list`, `example_characters`, `campaign_style_hint`.

---

## Pipeline stages

Each stage is a focused LLM call. Output of each validates before feeding the next.

### 1. `tone_and_pillars`

Input: one-line pitch, tone keywords, thematic pillars hint, inspiration list.

Output:
- A 2-3 sentence setting statement (ambient texture, not plot)
- 3-5 thematic pillars (concrete, specific)
- A short "content to include" list
- A short "content to avoid" list (merges user-provided with generated additions)

Written in a tone that matches the pitch.

### 2. `attributes`

Input: attribute flavor, one-line pitch, tone.

Output: exactly six attributes following `attributes.yaml` schema. Each with key, display, description, 2-4 example uses.

Validation:
- Exactly 6 entries
- Unique keys (lowercase snake_case)
- Unique display names
- Descriptions are distinct (no two attributes cover the same ground)
- Examples are specific to the genre, not generic

If the first generation has overlapping attributes (e.g., both "Physicality" and "Strength"), loop with a repair prompt.

### 3. `resources`

Input: resource flavor, attributes, tone.

Output: `resources.yaml` contents. Must include `hp_current` and `hp_max`. Beyond that, 2-4 additional resources that fit the genre.

Each resource has `key`, `display`, `kind`, `description`, `starting_value`, and kind-specific fields.

Validation:
- At least hp_current and hp_max present
- All keys unique, snake_case
- `kind` values are valid
- Threshold resources have valid threshold fields

### 4. `ability_categories`

Input: ability categories hint, attributes, resources, tone.

Output: 3-6 ability categories for `abilities.yaml`.

Each category has: key, display, description, activation, has_levels, level_names (if applicable), roll_attribute (if active), consequence_on_failure (if applicable), consequence_on_partial (if applicable).

Validation:
- 3-8 categories
- Unique keys
- `activation` valid
- `roll_attribute` references a real attribute key
- `consequence_on_*` references real resource keys
- At least one "weird" / genre-defining category if hint requested it

### 5. `ability_catalog`

Input: categories, attributes, resources, example characters, tone.

Generate abilities one at a time. 15-25 abilities. Distribute across categories — at least 2 per category, no more than 8 in any one category.

Each ability has: name, category, prerequisite, description, effect.

Validation:
- Prerequisites reference real attributes, real abilities, or `none`
- Effects reference real attributes, real resources, real categories
- No duplicate names
- Distribution is not lopsided

### 6. `character_template`

Input: attributes, resources.

Output: `character_template.json` matching the spec. Derive state fields from resources. Use the attribute keys from stage 2.

### 7. `gm_prompt_overlay`

Input: all prior.

Output: `gm_prompt_overlay.md` with all required sections:
- Setting and tone
- Thematic pillars
- Attribute guidance (when to call which attribute)
- Resource mechanics (when each ticks up/down, how they feel)
- Ability adjudication (one paragraph per category)
- Genre-specific NPC conventions
- Content to include / exclude
- Character creation rules (point-buy details, starting abilities count, starting equipment, starting resource values)

Validation:
- All six attribute keys appear in "Attribute guidance" section
- All resource keys from resources.yaml appear in "Resource mechanics"
- All category keys appear in "Ability adjudication"
- No references to attributes/resources/abilities that don't exist

If validation fails, run a repair pass: feed the overlay + missing references back to LLM, ask it to add the missing sections.

### 8. `failure_moves`

Input: tone, pillars, resources, example NPCs.

Output: `failure_moves.md` with 8-12 genre-flavored failure moves, plus a list of `[universal]` moves from the engine (hardcoded list — these are the same across all packs).

### 9. `example_hooks`

Input: all prior.

Output: `example_hooks.md` with 2-3 example opening hooks. Each is a 2-3 paragraph scene the player might open a campaign with, in the pack's tone. These are NOT used at runtime — they're reference material.

### 10. `generator_seed`

Input: all prior.

Output: `generator_seed.yaml` — default campaign seed for this pack. Genre, setting anchors, themes include/exclude, tone keywords, antagonist archetypes preferred.

### 11. `tone_doc` (optional)

Input: all prior.

Output: `tone.md` — expanded tone document. Soundtrack suggestions, writing samples, visual references. Optional; can be empty or skipped.

### 12. `pack_yaml`

Input: brief + all generated content.

Output: `pack.yaml` — metadata file with name, version, description, inspirations, created date.

### 13. `review_checklist`

Input: all prior, plus a log of which stages had to retry.

Output: `REVIEW_CHECKLIST.md` — specific to this pack, not generic. Items reflect where the generation had low confidence or high retry count. Example items:

```
- [ ] Attribute "Edge" has an abstract description — is it distinct from "Wits" in play?
- [ ] The "psionics" category has only 2 abilities; consider expanding if psionics are central
- [ ] The content_to_avoid list is short — any other themes you don't want the GM to generate?
- [ ] GM overlay section "Resource mechanics" was regenerated once — verify it feels right
- [ ] Example hook #2 is heavier on violence than the others — intentional?
```

---

## Validation

After all stages complete, run the full pack validation from `campaign_generator/pack.py`. If validation fails, treat as a hard error and log specifics. Do not write the pack directory — writing a broken pack just makes a mess.

On success, write all files to the output directory.

---

## Output files

```
<output_dir>/
├── pack.yaml
├── attributes.yaml
├── resources.yaml
├── abilities.yaml
├── character_template.json
├── gm_prompt_overlay.md
├── tone.md
├── failure_moves.md
├── example_hooks.md
├── generator_seed.yaml
├── REVIEW_CHECKLIST.md
└── _stages/                   # intermediate outputs, for debugging
    ├── tone_and_pillars.json
    ├── attributes.json
    ├── resources.json
    ├── ability_categories.json
    ├── ability_catalog.json
    ├── gm_prompt_overlay.json
    ├── failure_moves.json
    ├── example_hooks.json
    ├── generator_seed.json
    ├── calls.jsonl
    └── retries_log.txt
```

---

## Project layout

```
pack_generator/
├── pyproject.toml
├── README.md
├── examples/
│   └── space_opera_brief.yaml
├── prompts/
│   ├── 01_tone_and_pillars.md
│   ├── 02_attributes.md
│   ├── 03_resources.md
│   ├── 04_ability_categories.md
│   ├── 05_ability_catalog.md
│   ├── 06_gm_prompt_overlay.md
│   ├── 07_failure_moves.md
│   ├── 08_example_hooks.md
│   └── 09_review_checklist.md
├── pack_generator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── schemas.py
│   ├── pipeline.py
│   ├── stages/
│   │   ├── tone_and_pillars.py
│   │   ├── attributes.py
│   │   ├── resources.py
│   │   ├── ability_categories.py
│   │   ├── ability_catalog.py
│   │   ├── character_template.py
│   │   ├── gm_prompt_overlay.py
│   │   ├── failure_moves.py
│   │   ├── example_hooks.py
│   │   ├── generator_seed.py
│   │   └── review_checklist.py
│   └── writer.py            # writes all files to output dir
└── tests/
    ├── test_pipeline.py
    ├── test_stages.py
    ├── fixtures/
    │   └── canned_llm_responses/
    └── test_validation.py    # feeds generated packs into pack_generator.pack.validate()
```

The `common/` package (shared with campaign generator):

```
common/
├── __init__.py
├── llm.py               # OpenRouter client
├── pack.py              # pack loading and validation
└── schemas.py           # pydantic types shared across tools
```

Both generators import from `common/`.

---

## Design principles

1. **Packs are first drafts.** The generator is never the final word. `REVIEW_CHECKLIST.md` is integral, not optional.
2. **Hard validation.** A generated pack either passes spec validation or is not written. No half-valid output.
3. **Transparent retries.** When a stage retries due to validation failure, log the retry with reason. This surfaces LLM failure modes for tuning.
4. **Cheap iteration.** `--dry-run` with a cheap model must complete end-to-end so users can test briefs without burning tokens.
5. **Deterministic structure.** Same brief + same seed + same model → same pack (modulo LLM sampling variance). This matters for reproducibility.
6. **No hard-wrapped prose.** All generated markdown content (`gm_prompt_overlay.md`, `failure_moves.md`, `tone.md`, `example_hooks.md`, descriptions inside YAML files, etc.) must use newlines **only** as paragraph or list-item separators — never to wrap a paragraph at a fixed column width. Prose paragraphs are written as a single long line; the rendered output (and the campaign lorebook that bundles these files verbatim) needs unbroken paragraphs so SillyTavern displays them correctly. Every prompt that asks the LLM to produce prose must include this rule explicitly.

---

## Testing

- Replay fixtures: record a full pipeline run, monkeypatch the LLM client to return canned responses
- Assert: every generated pack passes `common.pack.validate()`
- Assert: pack files match expected structure
- Negative tests: malformed briefs, missing required fields, validation failures
- Integration: run the generator against the example `space_opera_brief.yaml`, then run the campaign generator against the produced pack, then verify the campaign imports into SillyTavern cleanly

---

## Verification before declaring done

- [ ] Generates a valid pack from the example space opera brief
- [ ] Generated pack passes `common.pack.validate()` without errors
- [ ] `REVIEW_CHECKLIST.md` reflects actual uncertainties from the run, not generic boilerplate
- [ ] Campaign generator accepts the produced pack without errors
- [ ] All tests pass with replay fixtures
- [ ] `--dry-run` completes end-to-end on a cheap model
- [ ] README documents the brief format with a worked example
