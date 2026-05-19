# Campaign Generator — Claude Code Brief

Build a Python tool that generates a complete, pre-authored TTRPG campaign from a **schema-v2** genre pack plus a campaign seed.

Hand this file to Claude Code along with [`01_SYSTEM_OVERVIEW.md`](01_SYSTEM_OVERVIEW.md), [`02_GENRE_PACK_SPEC.md`](02_GENRE_PACK_SPEC.md), [`04_EXTENSION_BRIEF.md`](04_EXTENSION_BRIEF.md), and [`09_SEED_FORMAT.md`](09_SEED_FORMAT.md) for context.

The v1 design (beats, node graphs, clue chains, stat-mode) is retired. The runtime that consumes the generator's output — the SillyTavern extension — tracks the story as **facts + threads + truths-revealed**, and the campaign generator produces artifacts that drop into that model.

---

## Goal

Given a v2 genre pack and a campaign seed, produce:

- A pre-authored situation the player can sit down with (premise, hook, opening scene).
- A campaign lorebook for SillyTavern, with the constant entries the extension binds to.
- Enough structured cast/scene material that the GM has somewhere to *go* without scripting beats.

Outputs land on disk; nothing runs at play time. The extension does the runtime work.

---

## Tech stack

- Python 3.11+, pydantic v2, pyyaml, typer, rich, httpx, tenacity, pytest.
- OpenRouter API via the shared `common.llm` client.
- Shared modules in `common/` — `common.pack` (v2 pack loader), `common.llm`, `common.settings`, `common.validation`, `common.env`.

---

## CLI

```
python -m campaign_generator \
    --genre genres/symbaroum_dark_fantasy/ \
    --seed my_seed.yaml \
    --output ./campaigns/my_first/
```

Flags:

- `--genre PATH` — pack directory (or pack name when `CAMPAIGN_GENERATOR_GENRES_BASE_DIR` is set).
- `--seed PATH` — campaign seed YAML.
- `--output PATH` — campaign directory to create.
- `--model STR` — OpenRouter model slug override.
- `--stages STR` — `all` or comma-separated stage names for partial re-runs.
- `--dry-run` — use the cheap dry-run model.
- `--random-seed INT` — picks the naming-diversity seed.
- `--init-seed PATH` — write an annotated blank seed for the chosen pack and exit.
- `--with-images` — chain the image generator after success.
- `--resume` — reuse the existing `--output` directory and its `stages/` cache instead of creating a sibling.

---

## Pipeline

Ten stages, run in order. Each LLM stage validates against a pydantic schema and may retry with a repair prompt.

1. **`premise`** — title, paragraphs, central conflict, tone, 3–5 thematic pillars.
2. **`plot_skeleton`** — 2–4 acts (each with title + goal; **no beats**), main antagonist, driving mystery, hook, escalation arc, 3–5-entry `thematic_spine`. Supporting cast briefs (name + archetype + narrative role).
3. **`factions`** — 2–4 factions with goals, methods, internal tensions, moral alignment. At least one ambiguous.
4. **`npcs`** — full NPC roster (6–30, seed-controlled). Each NPC has free-form story-mode `advantages` and optional `discovery_surfaces`. There is no closed ability catalog to validate against. Supporting-cast names from the plot stage are required to appear in the roster.
5. **`locations`** — 5–20 locations (seed-controlled). Sensory description (at least two senses), notable features, hidden elements, optional discovery surfaces. References to NPCs are validated.
6. **`truths`** — the campaign's **atomic truth set** (4–10). Each truth has an id, the truth text (1–2 sentences), an optional `hint` for the GM, and `adjacency_keys` (lowercase tokens the extension's pacing module matches against live threads and recent facts). The GM never sees the whole set; the runtime picks one at a time as a director's note.
7. **`complications`** — campaign-specific narrative complications (6–15). Layered on top of the pack's universal `complications.md` (which reaches the GM as `__pack_complications`). Vague phrases are rejected.
8. **`branches`** — 4–10 if/then contingencies referencing NPCs, locations, factions, or truth ids. References that don't resolve are dropped with a warning.
9. **`sample_characters`** — pregenerated story-mode characters in the v2 character template shape (`name`, `concept`, `advantages`, `disadvantages`, `belongings`, `relationships`, `hook_into_campaign`). No attributes, no abilities.
10. **Opening hook** — player-facing premise + opening scene + character-creation guidance. Run after cross-stage validation. Has a separate `pc_prior_knowledge` LLM call to render the "What you already know" section grounded in the campaign's NPCs and locations.

After the LLM stages:

- **Cross-stage validation** (`validation.validate_cross_stage`) — NPC faction affiliations, NPC relationships, location NPC references, branch references.
- **Lorebook assembly** (`lorebook.assemble_lorebook`).
- **Initial AN** — a small turn-0 placeholder; the runtime extension overwrites it on the first assistant message.

---

## Schemas

`schemas.py` (v2). Top-level models:

- `PremiseDocument`, `Antagonist`, `SupportingCastMember`, `ActOutline`, `PlotSkeleton` (with `thematic_spine` and no `acts[i].beats`).
- `Faction`, `FactionSet`.
- `NPCRelationship`, `NPC`, `NPCRoster` (NPCs carry `advantages` and `discovery_surfaces`; no `abilities` field).
- `SensoryDescription`, `Location`, `LocationCatalog` (no `plot_beats` field).
- `Truth`, `TruthSet`.
- `Complication`, `ComplicationSet`.
- `Branch`, `BranchPlan` (references resolve against NPC/location/faction/truth-id sets).
- `SampleCharacter`, `SampleCharacterSet` (v2 story-mode shape).
- `OpeningHookDocument`.

Retired v1 models: `Beat`, `ActOutline.beats`, `Node`, `NodeGraph`, `Clue`, `ClueGraph`, `InitialAuthorsNote`, `PCKnownNPCs`, `PackModeProfile`, `StoryModeProfile`. The schemas that survive are pruned of beat/ability/plot_beat references.

---

## Outputs

```
<output>/
├── opening_hook.txt
├── <campaign_title_slug>.json    # the campaign lorebook (includes the turn-0 AN seed as a disabled entry)
├── stages/
│   ├── premise.json
│   ├── plot_skeleton.json
│   ├── factions.json
│   ├── npcs.json
│   ├── locations.json
│   ├── truths.json
│   ├── complications.json
│   ├── branches.json
│   ├── sample_characters.json
│   ├── calls.jsonl
│   └── validation_log.txt
└── partials/
    ├── npcs.partial.json
    └── locations.partial.json
```

---

## Lorebook contract

The campaign lorebook JSON is the seam between the generator and the v3 extension. The extension binds to entries by exact `comment`:

| `comment` | constant | disabled | content |
|---|---|---|---|
| `__pack_gm_overlay` | ✓ | | full `gm_prompt_overlay.md` text |
| `__pack_complications` | ✓ | | pack's `complications.md` + campaign-specific complications |
| `__pack_reference` | ✓ | | JSON header (pack_name, version) + `advantages_disadvantages.md` |
| `__campaign_bible` | ✓ | | premise + central conflict + tone + thematic spine + antagonist |
| `__campaign_truths` | | ✓ | JSON array of authored truths (GM never sees) |
| `__pack_initial_authors_note` | | ✓ | turn-0 Author's Note seed (GM never sees; extension writes it into the AN on **Reset campaign**) |

Plus keyword-triggered entries:

- One `Faction: <name>` per faction.
- One `NPC: <name>` per NPC (public-tier). Optional `NPC Secret: <name>` (disabled by default; the extension's secrets module unlocks).
- One `Location: <name>` per location. Optional `Location Secret: <name>` (disabled by default).
- Optional `Branch Contingencies` and `Sample Characters` GM-facing reference entries (disabled by default).

Key-variant generation (drop honorifics, drop articles, strip trailing type tokens) is implemented in `lorebook._name_variants`.

---

## Cross-stage validation

`validation.validate_cross_stage` is called once after all stages complete. It checks:

- NPC `faction_affiliation` names a real faction or is null.
- NPC `relationships[].name` names a real NPC or `{{user}}`.
- Location `npc_names` resolve to real NPCs.
- Branch `references` resolve to a known NPC / location / faction / truth id.

The v1 validator also checked beat references, clue-graph topology, and ability-catalog membership; all retired.

---

## Pack access

The generator imports `common.pack.GenrePack` and reads:

- `pack.metadata` — display_name, pack_name, version.
- `pack.tone` — for premise / hook calibration.
- `pack.example_hooks` — for premise calibration.
- `pack.gm_prompt_overlay` — embedded as `__pack_gm_overlay`.
- `pack.complications` — embedded inside `__pack_complications`.
- `pack.advantages_disadvantages` — embedded inside `__pack_reference` and passed to the sample-characters stage.
- `pack.character_template` — passed to the sample-characters stage.
- `pack.naming` — fed to the naming-diversity seed.
- `pack.generator_seed_defaults` — merged into the seed before validation.

What the generator does NOT access: `pack.attributes`, `pack.resources`, `pack.abilities`. Those v1 fields don't exist on a v2 pack and are rejected at load time.

---

## Testing

```bash
cd campaign_generator
pytest
```

The current suite covers schema validation and seed loading. The full LLM-replay end-to-end test from v1 has been retired; its captured responses were v1-shaped. To restore: run the v2 pipeline against the real LLM, copy `stages/*.json` into `tests/fixtures/canned_llm_responses/`, and re-author a `test_pipeline_replays_to_valid_v2_campaign` test that asserts every expected output file is written and that the lorebook contains the five constant `__pack_*` / `__campaign_*` entries.

---

## Design principles

1. **Generator output is content + spine, not topology.** No flowchart, no clue graph, no beat sequence. Acts are thematic chapters; the GM is given the situation, not the route.
2. **Truths are the answer key, not a list of revealable items.** The GM never sees the whole set. The runtime picks one at a time when the player has earned it.
3. **NPCs and locations carry discovery surfaces, not edges.** Players brush against truths through fiction, not by traversing a graph.
4. **Hard validation.** Schema retries + cross-stage validation; the pipeline doesn't ship a half-valid campaign.
5. **Cheap iteration.** `--dry-run` runs end-to-end on a cheap model; `--resume` reuses cached stages.
6. **No stat-mode leakage.** Prompts and schemas reject dice / attribute / resource language.
