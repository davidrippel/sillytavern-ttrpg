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

Seed file (`my_seed.yaml`) extends the pack's `generator_seed.yaml`. Any fields specified here override the pack defaults. The user's seed is merged with the pack's seed, with user values winning.

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

Input: all prior.

Convert everything into SillyTavern lorebook entry objects. Each entry:
- `key`: array of trigger keywords (name, aliases, short forms). Include common misspellings.
- `content`: GM-facing notes written in the pack's tone. "Use this NPC's verbal tic. Their secret is X — reveal only if Y happens."
- `constant`: true for campaign bible and current-act entries
- `order`: priority (campaign bible highest, current act high, NPCs middle, locations lower)
- `comment`: human-readable label

Generate these entry types:
- Campaign bible (constant) — premise, themes, tone, GM overlay reference
- Current Act (constant) — Act 1 goals and beats
- One entry per NPC (keyword-triggered)
- One entry per location (keyword-triggered)
- One entry per faction (keyword-triggered)
- One entry per major clue or plot device (keyword-triggered)

Output the final structure as a valid SillyTavern World Info JSON file. The schema moves — verify against live SillyTavern docs during development.

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
│   └── seed.yaml                # example campaign seed
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
│   ├── __main__.py              # CLI entry
│   ├── pack.py                  # pack loading and validation (importable by pack generator too)
│   ├── schemas.py               # pydantic models for all stages
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
