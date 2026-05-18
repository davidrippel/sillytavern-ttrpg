# Pack Generator — Claude Code Brief

Build a Python tool that generates a complete, validated genre pack from a short human-written brief. This is a separate tool from the campaign generator but shares some infrastructure.

Hand this file to Claude Code along with [`01_SYSTEM_OVERVIEW.md`](01_SYSTEM_OVERVIEW.md), [`02_GENRE_PACK_SPEC.md`](02_GENRE_PACK_SPEC.md), and [`06_PACK_AUTHORING_GUIDE.md`](06_PACK_AUTHORING_GUIDE.md) for context.

The current target is **schema v2** (story-mode only — no dice, no attribute scores, no resource pools, no ability slots). The v1 pipeline (attributes / resources / abilities / failure_moves) is retired; the per-stage references below describe the v2 pipeline only.

---

## Goal

Given a short high-level genre brief, produce a full genre pack directory that validates against [`02_GENRE_PACK_SPEC.md`](02_GENRE_PACK_SPEC.md). The output is a first draft intended for human review and refinement — the `REVIEW_CHECKLIST.md` it produces alongside the pack guides that review.

Input: a genre brief YAML (small, human-written, see below).

Output: a complete pack directory with all files required by the spec, plus the review checklist.

**No bundling step.** The output is a directory of individual files, as specified in the spec. Python tools (campaign generator) read the directory directly. The SillyTavern extension reads the directory via its browser directory picker. There is no `pack.json` bundle; there is no import step; the pack is always the directory on disk.

---

## Tech stack

Same as the campaign generator:

- Python 3.11+, httpx, pydantic v2, pyyaml, typer, tenacity, rich, pytest
- OpenRouter API
- Shared modules in `common/` — `common.pack` (loader/validator), `common.llm` (LLM client), `common.settings`, `common.validation`, `common.progress`.

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
- `--output PATH` (required) — pack directory to create (must not exist, or must contain only `_stages/` from a prior run)
- `--model STR` — OpenRouter model slug
- `--stages STR` — `all` or comma-separated list (for re-running specific stages from cache)
- `--dry-run` — use cheap model

---

## Genre brief format

The brief is deliberately small. The user writes 15–40 lines; the generator fills in the rest.

```yaml
pack_name: space_opera_adventure
display_name: "Space Opera Adventure"
schema_version: 2

one_line_pitch: >
  Smugglers, derelict colonies, and ancient alien tech on the frontier
  of known space. Think Firefly meets Alien.

tone_keywords: [gritty, hopeful, wondrous, dangerous, blue-collar]

thematic_pillars_hint: >
  Community under pressure. The cost of freedom. What the old ones left
  behind. Generate 3-5 pillars in this vein.

content_to_avoid: [military_jingoism, grimdark_nihilism, racial_essentialism]

pressure_flavor: >
  The signature pressure is heat — the wanted-level / attention a crew
  accumulates from corp security, system patrols, and the people they
  cross. Concrete signs: a tail two berths over, a quiet meeting that
  goes silent when the crew enters, a credit freeze, an old contact who
  claims not to know them.

advantages_disadvantages_hint: >
  Axes: crew-role (pilot/mechanic/fixer/fighter/face), contact-network,
  shipboard, mark/debt. Example advantages: "best stick on the Verge
  route", "knows every fixer on Hadrian Station". Example disadvantages:
  "a corp warrant in the inner systems", "an unpaid syndicate debt".

complications_hint: >
  Heat climbs (corp notice, system patrols, fixer drops them). Ship
  takes a hit. Cargo is gone, moved, or different. Alien tech reacts
  strangely. A passenger turns out to be someone else. 10-15 in this
  vein, plus a "you succeed but..." list.

example_inspiration_list: >
  Firefly, Alien, The Expanse, early Star Wars, Outer Wilds.

example_characters: >
  A smuggler-captain with a haunted past. A xenoarcheologist who's seen
  too much. A mechanic who talks to ships.

campaign_style_hint: >
  Episodic adventures with an overarching mystery. Ships as homes.
```

Required fields: `pack_name`, `display_name`, `schema_version: 2`, `one_line_pitch`, `tone_keywords`, `pressure_flavor`, `advantages_disadvantages_hint`, `complications_hint`.

Optional but recommended: `thematic_pillars_hint`, `content_to_avoid`, `example_inspiration_list`, `example_characters`, `campaign_style_hint`.

**Retired v1 fields** (the loader raises `BriefError` if any appear): `attribute_flavor`, `resource_flavor`, `ability_categories_hint`.

---

## Pipeline stages

Each stage is a focused LLM call. Output of each validates before feeding the next. The pipeline lives in [`pack_generator/pipeline.py`](../pack_generator/pack_generator/pipeline.py); per-stage code in [`pack_generator/stages/`](../pack_generator/pack_generator/stages/); prompts in [`pack_generator/prompts/`](../pack_generator/prompts/).

### 1. `tone_and_pillars`

Input: brief.

Output: setting statement (2–3 sentences, ambient), 3–5 thematic pillars, content_to_include list, content_to_avoid list (merges user-supplied with generated additions).

### 2. `gm_prompt_overlay`

Input: brief, tone_and_pillars.

Output: eight required markdown sections (`setting_and_tone`, `thematic_pillars`, `resolving_actions`, `translating_pressures`, `npc_conventions`, `content_to_include`, `content_to_avoid`, `character_creation`). Under 1500 words target, hard cap 1800.

Validation:

- All eight sections non-empty.
- Total word count ≤ 1800.
- **No leaked stat-mode language.** The validator rejects any of `2d6`, `+1 to `, `attribute roll`, `make a roll`, or `status_update` in `resolving_actions`, `translating_pressures`, or `character_creation`. Story-mode is enforced structurally.

### 3. `advantages_disadvantages`

Input: brief, tone, overlay.

Output: 3–5 advantage axes and 3–5 disadvantage axes. Each axis: `title` plus 4–8 short phrase entries. Across all advantage axes, 20–35 entries total; across disadvantages, 15–25.

Validation:

- Each entry at least 3 words (no "strong", "smart", "lucky").
- Counts within bounds.

### 4. `complications`

Input: brief, tone, overlay.

Output: 10–15 genre-specific complications (each with `title` + `body`) + 6–12 "Success, but..." cost entries.

Validation:

- Counts within bounds.
- No vague phrases (`something happens`, `the gm decides`, `you fail`, `you lose`).

### 5. `character_template`

Deterministic. Produces the fixed v2 shape: `name`, `concept`, `advantages` (empty list), `disadvantages` (empty list), `belongings` (empty list), `relationships` (empty list), `notes`.

The pack author may post-edit to seed genre-appropriate default `belongings` if desired.

### 6. `example_hooks`

Input: brief, tone, overlay.

Output: 2–3 opening hooks. Each ends at a moment of choice (the validator checks for `?` or a known choice phrase in the last paragraph).

### 7. `naming`

Input: brief, tone, overlay.

Output: 8–14 `naming_registers` + 8–16 `district_flavors` used by the campaign generator's NPC/location stages. Skip-tolerant — the campaign generator has cross-genre fallbacks — but generated packs should always include this.

### 8. `generator_seed`

Input: brief, tone, overlay.

Output: default campaign seed (`setting_anchors`, `themes_include`, `themes_exclude`, `tone`, `antagonist_archetypes_preferred`, `num_npcs`, `num_locations`, `num_factions`, `num_truths`, `num_complications`). No `num_acts`, `clue_chain_density`, or `branch_points` — those v1 fields are retired and the validator rejects packs that carry them.

Validation: anchor specificity (cliché blocklist, ≥2 tokens), theme/tone consistency (no overlap or contradictions), ≥3 distinct antagonist archetypes, counts within stage-prompt ranges.

### 9. `pack_yaml`

Input: brief, tone, overlay.

Output: one-sentence description (≤ 280 chars). The rest of `pack.yaml` is templated from the brief: `schema_version: 2`, `version: 2.0.0`, `created` / `updated` set to today, inspirations parsed from the brief's `example_inspiration_list`.

### 10. `review_checklist`

Input: all prior + per-stage retries log.

Output: pack-specific checklist (≥4 items), grouped by section. Items reflect where generation had low confidence or high retry count; always at least one `Inspirations` item and one `Adjudication without dice` item.

### 11. Final validation

After all files are written, [`common.pack.load_pack`](../common/pack.py) parses the directory. The pack is only declared "done" if validation passes. The loader's checks:

- All required v2 files present.
- No legacy v1 files (`attributes.yaml`, `resources.yaml`, `abilities.yaml`, `failure_moves.md`).
- `pack.yaml` `schema_version == 2`.
- `character_template.json` has no legacy keys.
- `generator_seed.yaml` `genre` matches `pack.yaml` `pack_name`; no retired seed fields.
- `gm_prompt_overlay.md` contains all required section headers.

---

## Output files

```
<output_dir>/
├── pack.yaml
├── character_template.json
├── gm_prompt_overlay.md
├── tone.md
├── complications.md
├── advantages_disadvantages.md
├── example_hooks.md
├── generator_seed.yaml
├── naming.yaml
├── REVIEW_CHECKLIST.md
└── _stages/                   # intermediate outputs, for debugging
    ├── tone_and_pillars.json
    ├── gm_prompt_overlay.json
    ├── advantages_disadvantages.json
    ├── complications.json
    ├── character_template.json
    ├── example_hooks.json
    ├── naming.json
    ├── generator_seed.json
    ├── pack_yaml.json
    ├── review_checklist.json
    ├── calls.jsonl
    ├── validation_log.txt
    └── retries_log.txt
```

The three files the GM sees at runtime are embedded by the campaign generator into the campaign's lorebook as constant entries:

- `__pack_gm_overlay` ← `gm_prompt_overlay.md`
- `__pack_complications` ← `complications.md`
- `__pack_reference` ← `advantages_disadvantages.md`

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
│   ├── 04_advantages_disadvantages.md
│   ├── 06_gm_prompt_overlay.md
│   ├── 07_complications.md
│   ├── 08_example_hooks.md
│   ├── 09_generator_seed.md
│   ├── 10_pack_description.md
│   ├── 11_review_checklist.md
│   └── 12_naming.md
├── pack_generator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── brief.py
│   ├── schemas.py
│   ├── pipeline.py
│   ├── stages/
│   │   ├── tone_and_pillars.py
│   │   ├── gm_prompt_overlay.py
│   │   ├── advantages_disadvantages.py
│   │   ├── complications.py
│   │   ├── character_template.py
│   │   ├── example_hooks.py
│   │   ├── naming.py
│   │   ├── generator_seed.py
│   │   ├── pack_yaml.py
│   │   └── review_checklist.py
│   └── writer.py
└── tests/
    ├── test_brief.py
    ├── test_validation.py
    └── test_pipeline.py
```

The `common/` package (shared with campaign generator):

```
common/
├── __init__.py
├── llm.py               # OpenRouter client
├── pack.py              # pack loading and validation (v2)
└── ...                  # settings, env, progress, retrying, validation
```

Both generators import from `common/`.

---

## Design principles

1. **Packs are first drafts.** The generator is never the final word. `REVIEW_CHECKLIST.md` is integral, not optional.
2. **Hard validation.** A generated pack either passes spec validation or is not declared done.
3. **Transparent retries.** When a stage retries, log the reason in `_stages/validation_log.txt`.
4. **Cheap iteration.** `--dry-run` runs end-to-end on a cheap model so users can test briefs without burning tokens.
5. **No hard-wrapped prose.** All generated markdown content uses newlines only as paragraph or list-item separators. Every prompt that asks the LLM for prose says so explicitly.
6. **No stat-mode leakage.** The overlay schema and the GM base prompt both reject any leftover dice / attribute / resource / ability language. Story-mode is enforced structurally, not just by convention.

---

## Testing

The current suite (`pack_generator/tests/`) covers:

- Brief loading, including rejection of v1 fields and v1 `schema_version`.
- Schema-level validation for every v2 stage (overlay word count and stat-mode leak checks, complications vagueness, advantages/disadvantages totals, generator-seed anchor specificity and theme contradictions, example-hooks choice endings).
- A pipeline smoke test for the "refuses to overwrite a non-empty directory" guard.

The full LLM-replay pipeline test from v1 has been retired with the v1 schemas. A new replay-fixture set needs to be captured against a real v2 LLM run before that test can be restored — see the skipped `test_pipeline_replays_to_valid_pack` for the recipe.

Integration test (manual): run the generator against `examples/space_opera_brief.yaml`, then run the campaign generator against the produced pack, then verify the campaign imports into SillyTavern cleanly.

---

## Verification before declaring done

- [ ] Generates a valid v2 pack from the example space-opera brief.
- [ ] Generated pack passes `common.pack.load_pack()` without errors.
- [ ] `REVIEW_CHECKLIST.md` reflects actual uncertainties from the run, not generic boilerplate.
- [ ] Campaign generator accepts the produced pack without errors (once Phase 1 of the v2 campaign-generator migration is complete).
- [ ] All schema tests pass.
- [ ] `--dry-run` completes end-to-end on a cheap model.
- [ ] README documents the brief format with a worked example.
- [ ] No leftover references to attributes, abilities, resources, or dice anywhere in the pack output.
