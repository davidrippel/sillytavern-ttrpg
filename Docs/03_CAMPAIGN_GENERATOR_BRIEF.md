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
- OpenRouter as the LLM provider (https://openrouter.ai/api/v1/chat/completions). API key from env var `OPENROUTER_API_KEY`, with `.env` loading supported.
- Default model comes from env, not hard-coded. Current env keys:
  - `CAMPAIGN_GENERATOR_DEFAULT_MODEL`
  - `CAMPAIGN_GENERATOR_DRY_RUN_MODEL`
  - `CAMPAIGN_GENERATOR_DEFAULT_TEMPERATURE`
  - `OPENROUTER_API_URL`
  - `OPENROUTER_TIMEOUT_SECONDS`
  - `OPENROUTER_MAX_RETRIES`
  - `CAMPAIGN_GENERATOR_STAGE_MAX_RETRIES`
  - `CAMPAIGN_GENERATOR_GENRES_BASE_DIR`
  - `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR`
  - `CG_LLM_CLUE_GRAPH`, `CG_NODE_MODE` — *deprecated*. Node-mode is now the only supported clue/scenario model. These env vars are read for backwards compatibility but do not change behavior; the pipeline raises if `node_mode=False` is forced.
  - `IMAGE_GEN_MODEL`, `IMAGE_GEN_DIMENSION`, `IMAGE_GEN_ASPECT_RATIO`, `IMAGE_GEN_STYLE_OVERRIDE` — used by the sibling `image_generator` tool when rendering NPC portraits (also reachable via `--with-images`). `IMAGE_GEN_MODEL` is required when rendering and has no fallback. `IMAGE_GEN_STYLE_OVERRIDE` is optional and exists mainly to re-render an existing campaign in one consistent style without regenerating the pipeline output.

Web search during development to confirm: current OpenRouter API shape, current SillyTavern lorebook JSON schema, current model slug for `anthropic/claude-sonnet-4.5`.

---

## CLI interface

### Primary mode: generate a campaign

```
python -m campaign_generator \
    --genre genres/symbaroum_dark_fantasy/ \
    --seed my_seed.yaml \
    --output davokar_shadows \
    --model anthropic/claude-sonnet-4.5 \
    --stages all                           # or: premise,plot,factions
```

Flags:
- `--genre PATH` (required) — path to a validated genre pack directory
- `--seed PATH` (required) — campaign seed YAML
- `--output PATH` (optional if `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` is set) — output directory or output name
- `--model STR` — OpenRouter model slug
- `--stages STR` — `all` or comma-separated list of stage names to run (uses cached outputs for others)
- `--dry-run` — use a cheap model (e.g. `anthropic/claude-haiku-4.5`) for the whole pipeline
- `--random-seed INT` — reproducibility seed
- `--with-images` — after generation, call the image generator (see [`image_generator/README.md`](../image_generator/README.md)) to render NPC portraits into `<output>/npc_images/`. Requires `IMAGE_GEN_MODEL` in `.env`. Off by default. Image-gen failures are logged but do not fail the campaign run.
- `--nodes-mode` / `--beats-mode` — *deprecated*. Node-mode is the only supported mode; `--beats-mode` raises an error. The flag remains accepted for backwards compatibility.
- `--resume` — reuse the existing `--output` directory verbatim (and its cached `stages/*.json`) instead of allocating a fresh `_N` sibling. Use this to continue an interrupted run; the pipeline picks up at the first stage with no cache entry.

Model precedence is:
1. `model:` in the seed YAML
2. `--model`
3. `CAMPAIGN_GENERATOR_DRY_RUN_MODEL` when `--dry-run` is set
4. `CAMPAIGN_GENERATOR_DEFAULT_MODEL`

Path resolution rules:
- If `CAMPAIGN_GENERATOR_GENRES_BASE_DIR` is set, `--genre` may be either a full path or just the pack name.
- If `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` is set, a relative `--output my_campaign` is resolved under that base directory.
- If `--output` is omitted and `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` is set, the tool auto-generates a campaign directory name using timestamp + pack name + seed stem.
- Output name collisions are resolved by appending `_1`, `_2`, etc. Pass `--resume` to opt out and reuse the existing directory.

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

The repo also ships `.env.example` documenting all supported environment variables.

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

Implementation detail: acts and beats are first-class structured objects. Beats are not anonymous strings in the canonical model; they are assigned stable ids like `act1_beat1`, `act1_beat2`, etc. Final human-facing outputs render them as numbered beats like `1.1 ...`.

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
- `image_generation_prompt` — a self-contained text-to-image prompt (≤600 chars) used by the sibling [`image_generator`](../image_generator/README.md) tool to render an NPC portrait. The prompt must stand alone (no campaign context), match the genre's tone/style, and omit aspect-ratio or resolution directives (those are applied at render time from env config so the same prompt can be re-rendered at different sizes). It must start with a concrete full-body subject sentence that explicitly includes gender presentation, age range, hair, face/eyes, body/build or posture, clothing, and setting; later mood language must not replace visible traits.
- `image_style_hint` in the seed YAML is an optional hard style constraint for those portrait prompts. When present, the NPC stage should keep the same medium/look across the entire roster instead of drifting between sketch, painting, comic, cartoon, and photo language. When absent, the default fallback should bias toward full-body photorealistic portraits rather than illustration-style media.

The generator keeps a running roster and forbids duplicate names. NPCs should have varied demographics, voices, and agendas — if the first 3 NPCs are all wizened old men, reject and regenerate.

Current implementation constraints that must be treated as spec:
- Plot-critical named characters inferred from the plot skeleton must appear in the final NPC roster. This prevents later stages from referencing off-roster core characters.
- `{{user}}` is the only valid protagonist placeholder. Never invent a protagonist name.
- NPC relationships may reference `{{user}}`, the NPC themself, or another roster NPC. They should not introduce free-floating non-roster relationship targets.
- Each run computes a `diversity_seed` (cultural register + secondary register) from the seed's `random_seed` and an `avoid_names` list drawn from the most recent sibling campaigns under the campaigns base directory. Both are injected into the NPC prompt to push naming away from the model's default English-Latinate attractors and to prevent the same names recurring across consecutive campaigns. Implemented in `campaign_generator/diversity.py`. Registers are sampled from `pack.naming.naming_registers` (the pack's optional `naming.yaml`); when the pack omits the file, the module falls back to its built-in cross-genre default list.

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

Current implementation constraints:
- Locations are generated one at a time.
- `plot_beats` are normalized to canonical beat ids.
- `npc_names` must reference roster NPCs only; if the model invents a name, regenerate/repair the location instead of letting the bad reference through.
- The same `diversity_seed` used by the NPC stage (district flavor + naming style) and a location-specific `avoid_names` list (location names from the most recent sibling campaigns) are injected into the location prompt to steer away from repeated atmospheric English compounds ("The Velvet ___", "The Silk ___") and toward names rooted in the campaign's chosen cultural register. District flavors are sampled from `pack.naming.district_flavors`; naming styles remain in `diversity.py` as cross-genre defaults because they describe genre-agnostic *patterns* (trade + topographic feature, proprietor-possessive, etc.) rather than content.

### 6. `nodes`

Generates the node graph **before** the clue graph. Node-mode is the only supported campaign mode; the beat-mode clue path is no longer wired.

Input: premise, plot skeleton (acts + beats), NPC roster, location catalog.

Output: a `NodeGraph` whose nodes are organized per-act, with shared transition nodes between adjacent acts.

**Structural rules** (enforced by the stage and re-checked by the validator):
- Each act has `nodes_per_act` nodes (seed-configurable, default `5`, valid range `[3, 10]`).
- Per act: one start node, `nodes_per_act - 2` intermediate "points of interest", and one final node.
- **Transitions are shared**: act N's final node IS act N+1's start node — one node, two flags (`is_act_final=True` AND `is_act_start=True`). So with 3 acts × 5 nodes = 13 distinct nodes (5 + 4 + 4), not 15.
- The campaign's last act's final node is the **victory** (`is_victory=True`, no outbound role).
- Intermediate nodes are **unordered and optional**. The player may visit them in any order, or skip them entirely and beeline to the act's final node.

**Per-act LLM call sequence** (`1 + N*(1+intermediate_count)` calls for N acts):

1. *(Act 1 only)* `act_1_start` — designs the opening scene **and** picks act 1's relevant NPCs (3–7) and locations (2–5). Prompt: `08a_node_start.md`.
2. `act_N_final` — designs the act's dramatic culmination. For acts 2+ it also bundles that act's NPC/location selection. Receives all prior acts' final-node descriptions so escalation lands. Prompt: `08b_node_final.md`.
3..K. `act_N_intermediate_1`, `_2`, ... — designs each intermediate node, one at a time. Each prompt sees the act's start, the act's final, the act's NPC/location subset, and all previously-designed intermediates for this act (so the next one stays distinct). Prompt: `08c_node_intermediate.md`.

Each node carries:
- `id` (snake-case slug)
- `kind` (`location` / `npc_encounter` / `event`)
- `description`
- `act_number`
- `is_act_start`, `is_act_final`, `is_victory`
- `relevant_npcs` (subset of the act's NPC selection, filtered against the roster — silent drop of hallucinations)
- `relevant_location` (one of the act's locations)

The act-relevant subsets are picked by the LLM in the first prompt of each act and threaded into subsequent prompts so the act feels cohesive.

### 6.5. `clue_chains`

Input: validated node graph + NPC roster + location catalog.

Generate the clue graph deterministically. **No LLM call in the topology path** — only prose enrichment (`hint`/`reveals`) uses the LLM.

Each clue is a **directed edge between two nodes**:
- `id` — unique (`clue_01`, `clue_02`, ...)
- `found_at_node` — the source node id
- `points_to_node` — the target node id
- `found_at_type` — `npc` or `location`
- `found_at` — the NPC or location name where this clue is physically discovered
- `hint` — short (≤120 char) spoiler-light teaser describing what the clue *looks like* on the surface
- `reveals` — the spoiler prose (≤280 char)

**Structural rules** (validated):
- `found_at_node != points_to_node` (no self-loops).
- Source and target belong to the same act (with the shared transition node treated as belonging to its **outbound** act for outbound clues, and its **inbound** act for inbound clues).
- Every non-(act-1-start) node has **≥3 inbound clues** from same-act sources.
- Every non-victory node emits **≥1 outbound clue** (no stranding).
- Each act's start node emits **≥3 outbound clues** so the player has multiple leads upon entering an act.

When the per-act node count is small (e.g. `nodes_per_act=3`), the rules still hold via **duplicate edges**: clues are not uniquely keyed by `(source, target)`, so the start node can satisfy `≥3 outbound` by emitting 3 clues that all point to the same target. Likewise an inbound target with only one available source receives 3 clues all from that source.

**Clue anchoring** (where to find the clue): `_select_found_at` prefers the source node's own `relevant_npcs` / `relevant_location` (tier 1) — this keeps clue prose grounded to where the player physically is. If the source node has no relevance hints it falls back to the global pool (tier 2). Within a node, an `npc_encounter` kind prefers NPC anchors; `location` / `event` prefer locations. Anchors round-robin so the same NPC/location isn't reused for every clue at a node.

**Prose enrichment** (LLM, per clue): `_enrich_clue_prose` calls the LLM once per clue with the source/target node descriptions, the `found_at` NPC or location's context, and the campaign tone. The LLM rewrites only `hint` and `reveals`; structural fields are immutable. On any failure the clue keeps its templated text. Prompt: `06b_clue_prose.md`.

**Visibility**: the validation log emits `Clue graph: N clues, M enriched by LLM, K used template fallback`. The same line is sent through the progress callback.

### 7. `branches`

Input: all prior.

Generate 6-10 "if-then" contingencies:
- If player allies with faction X, then Y happens / Z shifts / W becomes available
- If player kills NPC A, then B, C, D
- If player fails to discover clue Q by end of Act 2, then R

Each branch notes consequences for later acts.

Current implementation constraints:
- Branch references may target factions, NPCs, clues, locations, and plot beat ids.
- The stage receives an explicit `reference_menu`.
- References are normalized after generation so beat text and simple faction aliases map back to canonical tokens.

### 8. `initial_authors_note`

Input: plot skeleton, opening hook content (and node graph in node-mode).

Output: the Author's Note text for Act 1 state. The section list depends on the campaign mode.

**Beat-mode** sections:
- Current Act: `Act 1: [title]`
- Current beat: rendered text of beat `1.1`
- Next beat: rendered text of beat `1.2` (or empty if act has only one beat)
- Discovered clues: `(none)` at start
- Available clues: `(none)` at start; populated at runtime from clue chain reachability
- Active threads: 2-3 initial hooks
- Recent beats: (empty at start)
- Reminders: anything the GM must not forget from the opening situation

The extension advances Current beat / Next beat at runtime by parsing
GM-emitted closure tags (`<<beat:LABEL:resolved>>`). The 2-beat window
is the spoiler-isolation mechanism — the GM never sees beats further
ahead than Next beat.

**Node-mode** sections (the only supported mode):
- Current Act: `Act 1: [title]`
- Reachable nodes: bullet list of the **targets of the start node's outbound clues** (the act-1 start node is implicitly visited on turn 1). At runtime this re-computes as the player moves between nodes and discovers more clues.
- Recently visited: `(none)` at start
- On-screen NPCs: `(none)` at start; populated at runtime as NPCs appear in scenes
- Discovered clues: `(none)` at start
- Available clues: **the start node's outbound clues** (id + hint) — non-empty at start so the GM can drop them on turn 1
- Active threads: 2-3 initial hooks
- Recent scenes: `(empty at start)`
- Reminders: anything the GM must not forget from the opening situation

In node-mode the extension does NOT advance a destination — Reachable nodes is a *menu* the player picks from by acting on clues, asking NPCs, going somewhere. Closure tags `<<node:ID:visited>>`, `<<node:ID:complete>>`, `<<npc:ID:state:KEY=VALUE,...>>`, and `<<clue:found:ID>>` mutate state. `Available clues` at runtime is a simple filter: undiscovered clues whose `found_at_node` matches the player's current node — no graph walk, no chain logic.

This becomes `initial_authors_note.txt` in the output.

### 9. `opening_hook`

Input: premise, Act 1 hook, tone, structured genre pack mechanics, seed protagonist hints, plus the full NPC roster and location catalog (used to build the proper-noun set for post-validation).

Output: the `opening_hook.txt` the player reads. Contains:
- Premise (safe to reveal)
- Tone statement
- Character creation guidance (specific to this campaign and genre pack — central pressure, reason to care about the opener, relevant attributes, ability categories, and resources)
- Opening scene (the first scene the GM will narrate, from the player's point of view — where they are, what they see, what prompts them to act)

MUST NOT contain: antagonist identity, clue chain, plot beats beyond Act 1 opener, NPC secrets, branch contingencies.

**Generation strategy: LLM-authored opening scene with deterministic post-validation and surgical retry.** The opening scene is generated by an LLM call against `09_opening_hook.md` (returning a single `opening_scene` field). After the call, a deterministic post-validator checks for known failure patterns:

- **Proper-noun casing** — every name in the NPC roster, location catalog, and premise/antagonist title must appear with exact canonical casing. Lowercase appearances of "thistle hold" or "valeria" are flagged.
- **Dangling-verb regex** — known ungrammatical shapes (`with a <noun> delivers`, similar `with a <noun> <verb>s` mismatches) are flagged.
- **Length sanity** — 80–800 chars.

On post-validation failure, the LLM is retried up to 3 times with the specific issues fed back as a repair note. After 3 failures, a deterministic auto-fix applies case-insensitive proper-noun substitution; if that resolves all remaining issues (or only casing issues remain), the corrected text ships and a note is written to `validation_log.txt`. Otherwise the pipeline falls back to a deterministic templated opening scene, also auto-corrected for proper-noun casing.

The other fields of the opening hook (premise, tone, character-creation guidance) are assembled deterministically. Character-creation guidance combines any seed protagonist archetype, the campaign's central conflict, the Act 1 hook, and a compact summary of the selected pack's attributes, ability categories, and non-static resources. Only the opening scene is LLM-authored. The early-pipeline partial draft (`partials/opening_hook.partial.txt`) uses the deterministic path because NPCs and locations don't yet exist when it runs.

Protagonist naming rule: every protagonist reference in all generated artifacts must use the exact SillyTavern placeholder `{{user}}`. Prompting should enforce this, and outputs should be sanitized afterward in case the model invents a protagonist name or uses generic phrases like "the protagonist" or "player character".

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
- Current Act (constant, high order) — Act 1 goals and explicitly numbered beats
- One **public** entry per NPC (keyword-triggered) — name, role, faction, description, voice, motivation, relationships, abilities. **Never includes the NPC's secret.**
- One **disabled** entry per NPC with a non-empty secret (`comment: "NPC Secret: <name>"`, `disable: true`, no trigger keys, `selective: false`) — contains the secret text and a one-line GM note explaining how to enable it. The GM unlocks the entry by setting `disable: false` once the reveal lands in play. This prevents secret content from being injected into the model's context whenever the NPC's name appears in chat — the previous behaviour spoiled mysteries on first NPC mention.
- One entry per location (keyword-triggered)
- One entry per faction (keyword-triggered)
- One entry per major clue or plot device (keyword-triggered)

**Trigger-key alias rules** (`_name_variants` in `lorebook.py`): every entity entry must have a `key` array that fires on the forms a player will plausibly type, not just the canonical name. The helper emits:
- the full canonical name
- the name with a leading article (`The`, `A`, `An`) stripped
- the form with a leading honorific stripped (`Sister Valeria` → `Valeria`; `Lord Cassius Valerius` → `Cassius` and `Cassius Valerius`); the honorific list covers `Sister, Brother, Father, Mother, Lord, Lady, Sir, Dame, Captain, Marshal, Foreman, Master, Mistress, Magister, Inquisitor, Baron(ess), Count(ess), Duke/Duchess, King, Queen, Prince(ss), Saint, Elder, High`
- for locations whose `type` is mentioned in the name (`The Gilded Raven Tavern` with `type: Tavern`), the bare form without the trailing type token (`Gilded Raven`)
- for entries whose name contains a parenthetical (`The Church of Prios (Thistle Hold Chapter)`), both the head and the parenthetical contents (`Church of Prios`, `Thistle Hold Chapter`)

A small stop-list of articles, prepositions, and generic nouns (`the, a, an, of, and, or, tavern, church, temple, shrine, guild, house, family, order, company, ...`) plus a 3-character minimum filters out useless single-token aliases.

Output the final structure as a valid SillyTavern World Info JSON file. The schema moves — verify against live SillyTavern docs during development.

The `__pack_*` naming convention is a hard requirement: the extension uses this prefix to identify pack-derived entries (for the compatibility check, and to distinguish them from campaign content in any hygiene dashboards).

### 11. `spoilers`

Input: all prior.

Output `spoilers/full_campaign.md`: human-readable dump of everything. Premise, plot, NPCs, locations, clue chains (rendered as a tree), branches, faction details, full cast roster.

This file is clearly labeled as spoilers. The user opens it only post-play, or when unsticking.

Two additional spoiler artifacts are emitted automatically after the `clue_chains` stage by a pure (non-LLM) renderer (`stages/graph.py`):

- `spoilers/campaign_graph.mmd` — Mermaid `flowchart TB` source: each act is a subgraph; node shape encodes `kind` (location/npc_encounter/event); `is_act_start` / `is_act_final` / gateway / `is_victory` get distinctive styling; clues are directed labeled edges; gating prerequisites are dotted edges; cross-act clue edges are thickened in red.
- `spoilers/campaign_graph.html` — self-contained viewer that loads Mermaid from CDN, embeds the source plus a JSON blob of full node/clue metadata, and wires hover handlers. Hovering a node or clue edge shows a floating details panel near the cursor (full description, triggers, relevant NPCs/location, gating, or hint/reveals). Zoom buttons (bottom-left) scale the SVG from 0.5×–4×; the graph fills the page width by default.

Like `full_campaign.md`, these reveal the whole topology and are clearly spoiler material.

---

## Validation between stages

Each stage's output is parsed into a pydantic model. If parsing fails, the stage retries with a repair prompt that includes the validation errors. Maximum 3 retries per stage before failing.

Cross-stage validation:
- NPCs in clue chains and branches must exist in the NPC roster
- Locations in clue chains and branches must exist in the location list
- Faction references in branches must resolve to known factions; simple aliases like dropping the leading `The` are normalized
- Branch references may also use canonical beat ids or beat text
- Abilities assigned to NPCs must exist in the pack's `abilities.yaml` catalog
- Location `plot_beats` must resolve to canonical beat ids or known beat text
- NPC relationships may use roster NPCs, the NPC themself, or `{{user}}`
- **NPC `faction_affiliation`** must be one of: `null`, the empty string, a recognized null token (`"None"`, `"none"`, `"Null"`, `"N/A"`, `"independent"`, `"unaffiliated"` — all treated as no faction), or a case-insensitive match to a real `Faction.name`. Strings that smuggle extra text after `None` (`"None (Formerly The Valerius Family)"`) are rejected as a NPC validation error and trigger the per-NPC repair loop. Accepted values are normalized to the canonical faction name (or `None` for null tokens) before being persisted to the roster.

Log all validation failures to `stages/validation_log.txt`.

Console/runtime behavior:
- Print timestamped progress messages as the pipeline runs.
- Print stage duration after each stage. Use seconds below 60s and minutes above that.
- Print OpenRouter usage summaries after each stage and at the end of the run:
  - total calls
  - total tokens
  - total cost/credits
- Log raw call responses plus OpenRouter `usage` blocks to `stages/calls.jsonl`.

---

## Output files

```
<output_dir>/
├── opening_hook.txt
├── initial_authors_note.txt
├── campaign_lorebook.json
├── partials/
│   ├── opening_hook.partial.txt
│   ├── initial_authors_note.partial.txt
│   ├── npcs.partial.json
│   ├── locations.partial.json
│   └── clue_chains.partial.json
├── spoilers/
│   ├── full_campaign.md
│   ├── campaign_graph.mmd     # Mermaid source for the acts/nodes/clues graph
│   └── campaign_graph.html    # standalone interactive viewer (hover nodes/clues for details)
├── stages/
│   ├── premise.json
│   ├── plot_skeleton.json
│   ├── factions.json
│   ├── npcs.json              # each NPC includes an `image_generation_prompt`
│   ├── locations.json
│   ├── nodes.json
│   ├── clue_chains.json
│   ├── branches.json
│   ├── calls.jsonl            # all LLM calls logged, including usage
│   └── validation_log.txt
└── npc_images/                # only present after running `image_generator` (or `--with-images`)
    ├── index.json
    └── <slug>.png
```

Artifact shape details that are now part of the spec:
- `plot_skeleton.json` stores beat objects with:
  - `id`
  - `label`
  - `text`
  - `rendered`
- location and clue artifacts include beat detail expansions for readability, while still preserving canonical beat ids for machine references.

---

## Quality requirements

- Every LLM call uses a focused, narrow system prompt in its own file under `prompts/`. NEVER a mega-prompt.
- Every stage validates previous stages' output. Fail loudly on inconsistencies.
- Handle rate limits and transient errors with exponential backoff (use `tenacity`).
- The final lorebook must import cleanly into SillyTavern without errors. Document the manual verification step in the README.
- `--dry-run` with a cheap model must complete the full pipeline so Claude Code can test end-to-end without expensive generations.
- Partial outputs must be written early enough that a failed run still leaves useful artifacts behind.
- Prefer preserving high-quality model output and repairing structure over discarding whole stages unnecessarily. The clue fallback is the current example of this policy.

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
│   ├── 06_clue_chains.md          # legacy LLM-first clue graph (gated by CG_LLM_CLUE_GRAPH=1)
│   ├── 06b_clue_prose.md          # default per-clue prose enrichment
│   ├── 07_branches.md
│   ├── 08_initial_an.md
│   ├── 09_opening_hook.md
│   ├── 10_lorebook.md
│   └── 11_spoilers.md
├── campaign_generator/
│   ├── __init__.py
│   ├── __main__.py              # CLI entry (both --seed and --init-seed modes)
│   ├── env.py                   # .env loading
│   ├── settings.py              # env-backed runtime settings
│   ├── paths.py                 # genre/output resolution
│   ├── pack.py                  # pack loading and validation (importable by pack generator too)
│   ├── schemas.py               # pydantic models for all stages
│   ├── seed.py                  # seed loading, validation, pack-default merging
│   ├── seed_template.py         # blank annotated seed file generation (--init-seed)
│   ├── llm.py                   # OpenRouter client
│   ├── pipeline.py              # stage orchestration
│   ├── artifacts.py             # enriched serialized stage artifacts
│   ├── placeholders.py          # protagonist placeholder normalization
│   ├── diversity.py             # cross-campaign name ledger + per-run cultural/naming seed
│   ├── stages/                  # one module per stage
│   │   ├── premise.py
│   │   ├── plot_skeleton.py
│   │   ├── factions.py
│   │   ├── npcs.py
│   │   ├── locations.py
│   │   ├── nodes.py
│   │   ├── node_generation.py
│   │   ├── clue_chains.py
│   │   ├── branches.py
│   │   ├── sample_characters.py
│   │   ├── initial_an.py
│   │   ├── opening_hook.py
│   │   ├── graph.py             # pure renderer: emits spoilers/campaign_graph.{mmd,html}
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
- Tests for:
  - example seed validation
  - output path auto-generation and collision suffixing
  - beat numbering/id rendering
  - protagonist placeholder sanitization
  - branch reference normalization
  - clue fallback behavior

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
