# Pack Generator

Generates a complete, validated TTRPG genre pack from a short human-written brief. Output is a directory of files conforming to `Docs/02_GENRE_PACK_SPEC.md` and consumable as-is by the campaign generator and the SillyTavern extension. There is no bundling step.

This is a sibling tool to `campaign_generator/` — both share infrastructure in `common/` (LLM client, pack validation, settings, env loader).

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
- `--model STR` — override the OpenRouter model slug (default: `anthropic/claude-sonnet-4.5`)
- `--stages STR` — `all` (default) or a comma-separated list of stage names to re-run from cache
- `--dry-run` — use the cheap dry-run model (default: `anthropic/claude-haiku-4.5`)

Each stage prints a progress line with elapsed time and OpenRouter usage:

```
[2026-05-01 14:32:24] Completed stage: attributes (12.4s, 1 call, 4831 tokens, 0.0142 credits)
```

## Pipeline

14 stages, run in order. Each LLM stage validates against a pydantic schema and retries with a repair prompt on failure.

1. `tone_and_pillars` — setting statement, 3-5 thematic pillars, content include/exclude
2. `attributes` — exactly 6 attributes
3. `resources` — `hp_current`, `hp_max`, plus 2-4 genre resources
4. `ability_categories` — 3-6 categories, with cross-validation against attributes/resources
5. `ability_catalog` — 15-25 abilities, distributed 2-8 per category
6. `character_template` — deterministic, derived from attributes + resources
7. `gm_prompt_overlay` — 9 markdown sections; a repair pass adds any missing references to attributes, resources, or categories
8. `failure_moves` — 8-12 genre-flavored moves plus the universal block
9. `example_hooks` — 2-3 opening hooks
10. `naming` — 8-14 naming registers + 8-16 district flavors used by the campaign generator's NPC/location stages
11. `generator_seed` — default campaign seed for this pack
12. `pack_yaml` — LLM writes the description; the rest is templated
13. `review_checklist` — pack-specific items, weighted by which stages had to retry
14. **Final validation** — the produced directory is parsed by `common.pack.load_pack`; the pack is only declared "done" if validation passes.

Per-stage outputs are cached in `<output>/_stages/`, alongside `calls.jsonl` (every LLM call), `validation_log.txt` (every retry reason), and `retries_log.txt` (retry counts by stage).

## Brief format

The brief is intentionally small — 15-40 lines. The pipeline fills in the rest.

Required:
- `pack_name` — lowercase snake_case
- `display_name`
- `schema_version: 1`
- `one_line_pitch`
- `tone_keywords` — a list
- `attribute_flavor`
- `resource_flavor`
- `ability_categories_hint`

Optional but recommended:
- `thematic_pillars_hint`
- `content_to_avoid`
- `example_inspiration_list`
- `example_characters`
- `campaign_style_hint`

A complete worked example: [`examples/space_opera_brief.yaml`](examples/space_opera_brief.yaml).

## Testing

```bash
cd pack_generator
pytest
```

The replay test (`tests/test_pipeline.py`) feeds the full pipeline canned LLM responses from `tests/fixtures/canned_llm_responses/space_opera/`, produces a complete pack, and asserts that `common.pack.load_pack()` accepts it. This guarantees that the pack generator's output is consumable by the campaign generator without any conversion.

## Design principles

1. **Packs are first drafts.** The generator is never the final word. `REVIEW_CHECKLIST.md` is integral, not optional.
2. **Hard validation.** A generated pack either passes spec validation or is not declared done.
3. **Transparent retries.** Every stage retry is logged with a reason in `_stages/validation_log.txt`.
4. **Cheap iteration.** `--dry-run` runs end-to-end on a cheap model so you can test briefs without burning tokens.
5. **No hard-wrapped prose.** Every prompt that asks the LLM to produce prose says so explicitly; the writer also defensively unwraps any column-wrapped paragraphs before writing.
