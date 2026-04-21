# Campaign Generator — Claude Code Brief

Build a Python tool that generates a complete, pre-authored TTRPG campaign from a genre pack plus a campaign seed.

Hand this file to Claude Code along with `01_SYSTEM_OVERVIEW.md` and `02_GENRE_PACK_SPEC.md` for context.

---

## Goal

Given a validated genre pack and a campaign seed YAML, produce:

- `opening_hook.txt` — the ONLY file the user reads before play. Premise, tone, character creation guidance, opening scene. No plot spoilers.
- `initial_authors_note.txt` — initial state for Act 1, pasted into SillyTavern's Author's Note on chat creation.
- `campaign_lorebook.json` — SillyTavern-importable lorebook with all NPCs, locations, factions, clues, and constant entries for campaign bible + current act.
- `spoilers/full_campaign.md` — human-readable dump of everything, for post-play reference or unsticking.
- `stages/*.json` — intermediate pipeline outputs for debugging and selective re-runs.

The user is expected to run this blind: they read only `opening_hook.txt` and `initial_authors_note.txt`.

---

## Tech stack

- Python 3.11+
- `httpx` for API calls (sync is fine)
- `pydantic` v2 for schema validation — highest-leverage library choice, use throughout
- `pyyaml` for pack files and seed files
- `typer` for the CLI
- `tenacity` for retries with exponential backoff
- `rich` for readable console output
- `pytest` for tests
- `pyproject.toml` + venv (or `uv`) for dependency management
- OpenRouter as the LLM provider (https://openrouter.ai/api/v1/chat/completions). API key from env var `OPENROUTER_API_KEY`.
- Default model: `anthropic/claude-sonnet-4.5`. Make configurable via CLI flag.

Web search during development to confirm: current OpenRouter API shape, current SillyTavern lorebook JSON schema, current model slug for `anthropic/claude-sonnet-4.5`.

---

## CLI interface

### Primary mode: generate a campaign

```
python -m campaign_generator \
    --genre genres/symbaroum_dark_fantasy/ \
    --seed my_seed.yaml \
    --output ./campaigns/davokar_shadows/ \
    --model anthropic/claude-sonnet-4.5 \
    --stages all                           # or: premise,plot,factions
```

Flags:
- `--genre PATH` (required) — path to a validated genre pack directory
- `--seed PATH` (required) — campaign seed YAML
- `--output PATH` (required) — output directory (will be created)
- `--model STR` — OpenRouter model slug, default `anthropic/claude-sonnet-4.5`
- `--stages STR` — `all` or comma-separated list of stage names to run (uses cached outputs for others)
- `--dry-run` — use a cheap model (e.g. `anthropic/claude-haiku-4.5`) for the whole pipeline
- `--random-seed INT` — reproducibility seed

Seed file extends the pack's `generator_seed.yaml`. Any fields specified in the seed override the pack defaults, except `themes_exclude` (which merges) and `strictness` (which merges field-by-field). The full seed format is specified in `09_SEED_FORMAT.md`.

### Secondary mode: generate a blank seed template

```
python -m campaign_generator \
    --init-seed my_seed.yaml \
    --genre genres/symbaroum_dark_fantasy/
```

Flags:
- `--init-seed PATH` — output path for the generated seed template
- `--genre PATH` (required) — path to a validated genre pack (used to populate pack-specific menus in comments)

This mode produces a blank annotated YAML file with every seed field present, each commented out, each with inline documentation. The user uncomments and edits what they want to control; the rest falls through to pack defaults.

The generated file must:
- Include every field from the seed schema (see `09_SEED_FORMAT.md` for the complete list)
- Have every optional field commented out (`# field: value`) with example values inline
- Include the `genre` field uncommented and pre-filled with the target pack's `pack_name`
- Include a comment at the top pointing to `09_SEED_FORMAT.md` for field documentation
- For fields that reference pack-specific menus (`antagonist_archetypes_preferred`, possibly others), list the pack's available options as a comment pulled from that pack's `generator_seed.yaml`
- Be a valid YAML file even when no fields are uncommented beyond `genre`

Implementation: read the pack's `generator_seed.yaml` and `pack.yaml`, then write a templated YAML file with comments. Template structure lives in `campaign_generator/seed_template.py` or equivalent. Keep the template close to `09_SEED_FORMAT.md`'s structure so the documentation and the template stay synchronized.

---

## Shipped example seeds

The repo must include a set of pre-written example seed files under `examples/`, targeting the Symbaroum example pack (`08_EXAMPLE_PACK_SYMBAROUM.md` rendered as a real pack directory). These are static files committed to the repo — not generated at runtime. Their purpose is to let a new user run the generator immediately, without having to understand the seed format first.

Required example files, each a valid seed for the Symbaroum pack:

### `examples/seed_minimal.yaml`

Only the required `genre` field plus a single `campaign_pitch`. Demonstrates that most fields can be omitted and the generator still works, falling through to pack defaults. Target: 5-10 lines total.

### `examples/seed_balanced.yaml`

The recommended starting point for a user writing their first real seed. Includes `genre`, `campaign_pitch`, `themes_include`, `protagonist_archetype`, and `antagonist_archetypes_preferred`. Omits everything else. Target: 20-30 lines.

This is the file most users will copy and edit. It should be the example most clearly documented and most carefully tuned — a user who copies this file, edits a few values, and runs the generator should get a good first campaign.

### `examples/seed_maximum.yaml`

A fully-specified seed covering every field documented in `09_SEED_FORMAT.md`. Includes specific `setting_anchors`, `protagonist_known_facts`, `opening_hook_seed`, `tone_modifiers`, structural fields (`num_acts`, `num_npcs`, etc.), and a worked `strictness` block. Target: 60-80 lines.

This example is less for copying and more for reference — it shows what every field looks like filled in, so a user can see how a particular field is meant to be used before writing their own.

### Content requirements for all three

All three examples must:
- Target the Symbaroum pack specifically (`genre: symbaroum_dark_fantasy`)
- Be different campaigns — not minimal/balanced/maximum versions of the *same* campaign, which would make the maximum example redundant. Three distinct premises showcase the pack's range.
- Pass seed validation against the example Symbaroum pack
- Run end-to-end through the generator pipeline without errors (verified in tests)
- Include a comment block at the top explaining what the example is, which tier of specificity it represents, and when to copy it

### README integration

The main `README.md` must include a "Quickstart" section using these examples. The flow shown should be:

```
cp examples/seed_balanced.yaml my_seed.yaml
# edit my_seed.yaml
python -m campaign_generator \
    --genre genres/symbaroum_dark_fantasy/ \
    --seed my_seed.yaml \
    --output ./my_first_campaign/
```

Five steps from fresh clone to generated campaign. This is the priority user experience — the `--init-seed` mode is for users working with new/custom packs once they understand the format.

### Tests

A test must exist for each example file: load the example, validate against the example Symbaroum pack, assert validation passes. This prevents regressions where a schema change silently breaks a shipped example.

---

## Pipeline stages

Each stage is a narrow, focused function. Each has its own prompt template file in `prompts/`. Each validates its output with a pydantic schema before passing it to the next stage.

### 1. `premise`

Input: pack tone, thematic pillars, example hooks, merged seed.

Output: premise document with:
- 2-paragraph campaign premise
- central conflict (1-2 sentences)
- tone statement (inherits pack tone, specialized for this campaign)
- 3-5 thematic pillars (inherits from pack, may add campaign-specific)

### 2. `plot_skeleton`

Input: premise + pack overlay.

Output: 4-act structure with:
- Act goals (what the protagonist is trying to do in each act)
- Act beats (3-5 beats per act)
- Main antagonist: name, motivation, secret, relationship to protagonist
- The driving mystery or question
- The hook (how the protagonist is drawn in)
- Escalation arc (how stakes rise across acts)

### 3. `factions`

Input: premise + plot skeleton + pack tone.

Output: 2-4 factions with:
- Name, description, goals, methods
- Internal tensions
- Relationship to the plot (are they helping, hindering, ambiguous?)
- At least one faction must be morally ambiguous

### 4. `npcs`

Input: all prior.

Generate NPCs one at a time in separate LLM calls (quality degrades if you batch). 8-12 NPCs covering all acts.

Each NPC:
- Name, role, faction affiliation
- Physical description (sensory, memorable)
- Manner of speaking (1-2 distinctive verbal tics or patterns)
- Motivation (what they want)
- Secret (what they're hiding)
- Relationships to other NPCs (cite by name)
- Abilities from pack catalog if supernatural/specialized (cite by name from `abilities.yaml`)

The generator keeps a running roster and forbids duplicate names. NPCs should have varied demographics, voices, and agendas — if the first 3 NPCs are all wizened old men, reject and regenerate.

### 5. `locations`

Input: all prior.

Generate locations one at a time. 6-10 locations.

Each location:
- Name, type (tavern, ruin, forest, etc.)
- Sensory description: sight, sound, smell (at minimum two of three)
- Notable features (things that matter mechanically or narratively)
- Hidden elements (what a careful search reveals)
- Which NPCs can be found here
- Which plot beats occur here

### 6. `clue_chains`

Input: all prior.

Generate an explicit clue graph as structured JSON, not prose.

Each clue:
- `id` (unique)
- `found_at` — location or NPC reference
- `reveals` — what the clue tells the protagonist
- `points_to` — next clue id(s), NPC, or location

Constraints (validated by pydantic):
- Every clue must be reachable from the opening hook (graph connectivity)
- Every major plot beat must have at least two paths leading to it (so player choices don't dead-end the investigation)
- No orphan clues (clues pointing to nothing)
- No missing references (a clue pointing to NPC X requires X to exist)

If the first generation fails these constraints, loop: feed the constraint failures back to the LLM as a repair prompt.

### 7. `branches`

Input: all prior.

Generate 6-10 "if-then" contingencies:
- If player allies with faction X, then Y happens / Z shifts / W becomes available
- If player kills NPC A, then B, C, D
- If player fails to discover clue Q by end of Act 2, then R

Each branch notes consequences for later acts.

### 8. `initial_authors_note`

Input: plot skeleton, opening hook content.

Output: the Author's Note text for Act 1 state. Sections:
- Current Act: Act 1 — [title]
- Pending beats: first 2-3 beats from Act 1
- Active threads: 2-3 initial hooks
- Recent beats: (empty at start)
- Reminders: anything the GM must not forget from the opening situation

This becomes `initial_authors_note.txt` in the output.

### 9. `opening_hook`

Input: premise, Act 1 hook, tone, character creation guidance from pack.

Output: the `opening_hook.txt` the player reads. Contains:
- Premise (safe to reveal)
- Tone statement
- Character creation guidance (specific to this campaign — what kinds of characters fit, what background elements to consider)
- Opening scene (the first scene the GM will narrate, from the player's point of view — where they are, what they see, what prompts them to act)

MUST NOT contain: antagonist identity, clue chain, plot beats beyond Act 1 opener, NPC secrets, branch contingencies.

### 10. `lorebook_assembly`

Input: all prior, plus the full pack contents.

Convert everything into SillyTavern lorebook entry objects. Each entry:
- `key`: array of trigger keywords (name, aliases, short forms). Include common misspellings.
- `content`: GM-facing notes written in the pack's tone. "Use this NPC's verbal tic. Their secret is X — reveal only if Y happens."
- `constant`: true for campaign bible, current-act, and pack-derived entries
- `order`: priority (pack overlay highest, campaign bible high, current act high, NPCs middle, locations lower)
- `comment`: human-readable label

Generate these entry types:

**Pack-derived constant entries** (inserted by the generator from pack files; these let the extension remain pack-unaware at runtime and let the GM see pack content without the extension):

- `__pack_gm_overlay` (constant, highest order) — full verbatim text of the pack's `gm_prompt_overlay.md`. This is how the genre overlay reaches the GM. The `__` prefix marks this as machinery, not campaign content. Keyword-triggered matching should not fire on this entry's content.
- `__pack_failure_moves` (constant, high order) — full verbatim text of the pack's `failure_moves.md`. Lets the GM select from genre-flavored moves on 2-6 rolls.
- `__pack_reference` (metadata-only, not injected into prompts) — a machine-readable entry containing `pack_name`, `pack_version`, `display_name` from `pack.yaml`. The extension reads this on chat open to perform the compatibility check (see `04_EXTENSION_BRIEF.md`). Its content is a JSON blob. It must have `constant: false` and no trigger keywords so it never fires into the GM's context — the extension reads it directly from the lorebook via SillyTavern's World Info API, not through prompt injection.

**Campaign-specific entries**:

- Campaign bible (constant, high order) — premise, themes, campaign-specific tone calibrations (not the pack's tone — those are in the overlay)
- Current Act (constant, high order) — Act 1 goals and beats
- One entry per NPC (keyword-triggered)
- One entry per location (keyword-triggered)
- One entry per faction (keyword-triggered)
- One entry per major clue or plot device (keyword-triggered)

Output the final structure as a valid SillyTavern World Info JSON file. The schema moves — verify against live SillyTavern docs during development.

The `__pack_*` naming convention is a hard requirement: the extension uses this prefix to identify pack-derived entries (for the compatibility check, and to distinguish them from campaign content in any hygiene dashboards).

### 11. `spoilers`

Input: all prior.

Output `spoilers/full_campaign.md`: human-readable dump of everything. Premise, plot, NPCs, locations, clue chains (rendered as a tree), branches, faction details, full cast roster.

This file is clearly labeled as spoilers. The user opens it only post-play, or when unsticking.

---

## Validation between stages

Each stage's output is parsed into a pydantic model. If parsing fails, the stage retries with a repair prompt that includes the validation errors. Maximum 3 retries per stage before failing.

Cross-stage validation:
- NPCs in clue chains and branches must exist in the NPC roster
- Locations in clue chains and branches must exist in the location list
- Faction references must match faction names exactly
- Abilities assigned to NPCs must exist in the pack's `abilities.yaml` catalog

Log all validation failures to `stages/validation_log.txt`.

---

## Output files

```
<output_dir>/
├── opening_hook.txt
├── initial_authors_note.txt
├── campaign_lorebook.json
├── spoilers/
│   └── full_campaign.md
└── stages/
    ├── premise.json
    ├── plot_skeleton.json
    ├── factions.json
    ├── npcs.json
    ├── locations.json
    ├── clue_chains.json
    ├── branches.json
    ├── calls.jsonl            # all LLM calls logged
    └── validation_log.txt
```

---

## Quality requirements

- Every LLM call uses a focused, narrow system prompt in its own file under `prompts/`. NEVER a mega-prompt.
- Every stage validates previous stages' output. Fail loudly on inconsistencies.
- Handle rate limits and transient errors with exponential backoff (use `tenacity`).
- The final lorebook must import cleanly into SillyTavern without errors. Document the manual verification step in the README.
- `--dry-run` with a cheap model must complete the full pipeline so Claude Code can test end-to-end without expensive generations.

---

## Project layout

```
campaign_generator/
├── pyproject.toml
├── README.md
├── examples/
│   ├── seed_minimal.yaml        # tier 1: genre + pitch only, ~5-10 lines
│   ├── seed_balanced.yaml       # tier 2: recommended starting point, ~20-30 lines
│   └── seed_maximum.yaml        # tier 3: every field worked, ~60-80 lines
├── prompts/
│   ├── 01_premise.md
│   ├── 02_plot_skeleton.md
│   ├── 03_factions.md
│   ├── 04_npc.md
│   ├── 05_location.md
│   ├── 06_clue_chains.md
│   ├── 07_branches.md
│   ├── 08_initial_an.md
│   ├── 09_opening_hook.md
│   ├── 10_lorebook.md
│   └── 11_spoilers.md
├── campaign_generator/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry (both --seed and --init-seed modes)
│   ├── pack.py                  # pack loading and validation (importable by pack generator too)
│   ├── schemas.py               # pydantic models for all stages
│   ├── seed.py                  # seed loading, validation, pack-default merging
│   ├── seed_template.py         # blank annotated seed file generation (--init-seed)
│   ├── llm.py                   # OpenRouter client
│   ├── pipeline.py              # stage orchestration
│   ├── stages/                  # one module per stage
│   │   ├── premise.py
│   │   ├── plot_skeleton.py
│   │   ├── factions.py
│   │   ├── npcs.py
│   │   ├── locations.py
│   │   ├── clue_chains.py
│   │   ├── branches.py
│   │   ├── initial_an.py
│   │   ├── opening_hook.py
│   │   └── spoilers.py
│   ├── lorebook.py              # assembly into SillyTavern format
│   └── validation.py            # cross-stage validators
└── tests/
    ├── test_pack_validation.py
    ├── test_schemas.py
    ├── test_seed.py             # seed loading + pack merging tests
    ├── test_seed_template.py    # blank-template generation tests
    ├── test_pipeline.py
    ├── fixtures/
    │   └── canned_llm_responses/  # for replay tests
    └── test_lorebook_output.py
```

---

## Testing

Critical: use a replay fixture so tests don't burn OpenRouter credits. Approach:

- Record a full pipeline run against real LLM once, saving every response to `tests/fixtures/canned_llm_responses/<stage>.json`.
- Test suite monkeypatches the `llm.call()` function to return canned responses matching the call hash (prompt content hash).
- Tests assert on pydantic validation, cross-stage consistency, and lorebook JSON structure.

Also include:
- Unit tests for pack loading and validation (run against the example pack in `08_EXAMPLE_PACK_SYMBAROUM.md` rendered as a real pack directory)
- Unit tests for schema validation with malformed inputs
- Integration test: full pipeline with replay fixtures, assert all output files exist and parse

---

## Verification before declaring done

- [ ] Full pipeline runs against example Symbaroum pack without errors
- [ ] `campaign_lorebook.json` imports cleanly into a fresh SillyTavern instance
- [ ] `opening_hook.txt` contains no spoilers (manual review — LLM-assisted check via final safety prompt)
- [ ] `initial_authors_note.txt` describes only Act 1 opening state
- [ ] All cross-stage references resolve (no dangling NPC/location/ability names)
- [ ] Tests pass with replay fixtures
- [ ] `--dry-run` mode completes in reasonable time on a cheap model
- [ ] `--init-seed` produces a valid YAML file against the example Symbaroum pack
- [ ] The generated blank seed, after uncommenting only the `genre` field, runs through the full pipeline without validation errors (smoke test for pack-default fall-through)
- [ ] Seed validation errors are clear: invalid `genre`, unknown `antagonist_archetypes_preferred`, contradictory themes include/exclude — each produces a specific message naming the field
- [ ] All three shipped examples (`seed_minimal.yaml`, `seed_balanced.yaml`, `seed_maximum.yaml`) exist, validate against the Symbaroum pack, and describe three distinct campaigns
- [ ] At least one of the three examples has been run through the full pipeline end-to-end with real LLM calls to confirm the resulting campaign is coherent (this is a manual check, not an automated test — the output gets eyeball-reviewed for tone, clue graph sanity, and NPC distinctness)
- [ ] README quickstart section exists and demonstrates the `cp examples/seed_balanced.yaml` flow
