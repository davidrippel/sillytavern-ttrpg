# Pack Generator

Generates a complete, validated TTRPG genre pack from a short human-written brief. Output is a directory of files conforming to [`Docs/02_GENRE_PACK_SPEC.md`](../Docs/02_GENRE_PACK_SPEC.md) and consumable as-is by the campaign generator and the SillyTavern extension. There is no bundling step.

This is a sibling tool to `campaign_generator/` — both share infrastructure in `common/` (LLM client, pack validation, settings, env loader).

The generator emits **schema v2** packs (story-mode only — no dice, no attributes, no resources, no abilities). The v1 (stat-mode) pipeline is retired; see the migration section in [`Docs/02_GENRE_PACK_SPEC.md`](../Docs/02_GENRE_PACK_SPEC.md#migrating-a-v1-pack-to-v2).

## Install

```bash
# From the repo root, in your venv (Python 3.11+):
pip install -e ./pack_generator
```

Both tools read API credentials and other settings from a single `.env` at the repo root (see `.env.example`).

## Usage

```bash
python -m pack_generator \
    --brief pack_generator/examples/space_opera_brief.yaml \
    --output genres/space_opera_adventure/
```

Flags:
- `--brief PATH` (required) — the genre brief YAML
- `--output PATH` (required) — the pack directory to create. Must not exist or must contain only `_stages/` from a previous run (so re-running with `--stages` works against cached output).
- `--model STR` — override the OpenRouter model slug
- `--stages STR` — `all` (default) or a comma-separated list of stage names to re-run from cache
- `--dry-run` — use the cheap dry-run model

Each stage prints a progress line with elapsed time and OpenRouter usage:

```
[2026-05-16 14:32:24] Completed stage: gm_prompt_overlay (12.4s, 1 call, 4831 tokens, 0.0142 credits)
```

## Pipeline

Ten stages, run in order. Each LLM stage validates against a pydantic schema and retries with a repair prompt on failure.

1. `tone_and_pillars` — setting statement, 3–5 thematic pillars, content include/exclude
2. `gm_prompt_overlay` — eight required markdown sections (setting, pillars, resolving actions, translating pressures, NPC conventions, content in/out, character creation). The schema rejects overlays that leak stat-mode language ("2d6", "+1 to", "make a roll", "STATUS_UPDATE")
3. `advantages_disadvantages` — 3–5 advantage axes and 3–5 disadvantage axes; 20–35 advantage entries and 15–25 disadvantage entries total. Each entry must be at least 3 words.
4. `complications` — 10–15 genre-specific narrative complications + 6–12 "success but..." cost entries
5. `character_template` — deterministic, fixed v2 shape (`name`, `concept`, `advantages`, `disadvantages`, `belongings`, `relationships`, `notes`)
6. `example_hooks` — 2–3 opening hooks, each ending at a moment of choice
7. `naming` — 8–14 naming registers + 8–16 district flavors used by the campaign generator's NPC/location stages
8. `generator_seed` — default campaign seed for this pack (`num_truths`, `num_complications`, `num_factions`, plus tone / themes / anchors / antagonist archetypes)
9. `pack_yaml` — LLM writes the description; the rest is templated (schema_version 2, version 2.0.0)
10. `review_checklist` — pack-specific items, weighted by which stages had to retry
11. **Final validation** — the produced directory is parsed by `common.pack.load_pack`; the pack is only declared "done" if validation passes.

Per-stage outputs are cached in `<output>/_stages/`, alongside `calls.jsonl` (every LLM call), `validation_log.txt` (every retry reason), and `retries_log.txt` (retry counts by stage).

## Brief format

The brief is intentionally small — 15–40 lines. The pipeline fills in the rest.

Required:
- `pack_name` — lowercase snake_case
- `display_name`
- `schema_version: 2`
- `one_line_pitch`
- `tone_keywords` — a list
- `pressure_flavor` — the genre's signature accumulating pressure (corruption / heat / sanity / ship damage / exposure); a paragraph naming what it is, what feeds it, and what the player sees when it climbs
- `advantages_disadvantages_hint` — what axes the genre uses (bodily / mystical / crew-role / contact-network) plus 4–8 example phrases per axis
- `complications_hint` — what kinds of narrative complications fit the genre, with 6–10 examples

Optional but recommended:
- `thematic_pillars_hint`
- `content_to_avoid`
- `example_inspiration_list`
- `example_characters`
- `campaign_style_hint`

A complete worked example: [`examples/space_opera_brief.yaml`](examples/space_opera_brief.yaml).

**v1 fields rejected**: `attribute_flavor`, `resource_flavor`, `ability_categories_hint` (and `schema_version: 1`). The story-mode runtime has no attribute scores, resource pools, or ability slots, so those hints have nothing to drive. The loader raises a `BriefError` with a migration hint when it sees them.

## Outputs

A successful run produces a directory matching [`Docs/02_GENRE_PACK_SPEC.md`](../Docs/02_GENRE_PACK_SPEC.md):

```
<output>/
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
└── _stages/                # per-stage cache + LLM call log + retry log
```

The three files the GM sees at runtime — `gm_prompt_overlay.md`, `complications.md`, `advantages_disadvantages.md` — are embedded by the campaign generator into the campaign's lorebook as `__pack_gm_overlay`, `__pack_complications`, and `__pack_reference`.

## Testing

```bash
cd pack_generator
pytest
```

The current suite covers schema validation and brief loading. The full LLM-replay test from v1 has been retired because its captured responses were v1-shaped; a new replay fixture set needs to be captured against a real v2 run before the end-to-end test can be restored. To capture: run the pipeline against the real LLM, copy the per-stage JSON files from `<output>/_stages/` into `tests/fixtures/canned_llm_responses/<pack>/`, and re-enable the skipped test in `test_pipeline.py`.

## Design principles

1. **Packs are first drafts.** The generator is never the final word. `REVIEW_CHECKLIST.md` is integral, not optional.
2. **Hard validation.** A generated pack either passes spec validation or is not declared done.
3. **Transparent retries.** Every stage retry is logged with a reason in `_stages/validation_log.txt`.
4. **Cheap iteration.** `--dry-run` runs end-to-end on a cheap model so you can test briefs without burning tokens.
5. **No hard-wrapped prose.** Every prompt that asks the LLM to produce prose says so explicitly; the writer also defensively unwraps any column-wrapped paragraphs before writing.
6. **No stat-mode leakage.** The overlay schema and the GM prompt both reject any leftover dice / attribute / resource / ability language. Story-mode is enforced structurally, not just by convention.
