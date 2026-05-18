# Campaign Generator

Python tool for generating a complete, pre-authored TTRPG campaign from a validated **schema-v2** (story-mode) genre pack plus a campaign seed.

The v1 design (beats, nodes, clue chains, stat-mode) is retired — see [`Docs/03_CAMPAIGN_GENERATOR_BRIEF.md`](../Docs/03_CAMPAIGN_GENERATOR_BRIEF.md) for the v2 contract and [`solo-ttrpg-assistant/CHANGELOG.md`](../solo-ttrpg-assistant/CHANGELOG.md) for the runtime that consumes the new output.

## Quickstart

1. Create a virtual environment and install dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

2. Copy the recommended example seed:

```bash
cp examples/seed_balanced.yaml my_seed.yaml
```

3. Create `.env` from the example and add your OpenRouter key. `.env` lives at the **repo root** so it's shared with the pack generator.

```bash
cp ../.env.example ../.env
```

4. Edit `my_seed.yaml`.
5. Run the generator:

```bash
python -m campaign_generator \
    --genre genres/symbaroum_dark_fantasy/ \
    --seed my_seed.yaml \
    --output ./campaigns/my_first_campaign/
```

6. Read `opening_hook.txt`; import `campaign_lorebook.json` into the SillyTavern chat that runs the GM. The runtime extension regenerates the Author's Note from per-turn state, so `initial_authors_note.txt` is a turn-0 placeholder.

If `CAMPAIGN_GENERATOR_GENRES_BASE_DIR` is set in `.env`, `--genre` can also be just the pack name.

## Seed Template

Generate a blank annotated seed file:

```bash
python -m campaign_generator \
    --init-seed my_seed.yaml \
    --genre symbaroum_dark_fantasy
```

## Outputs

A successful run writes:

- `opening_hook.txt` — player-facing premise, tone, character-creation guidance pointing at the pack's `advantages_disadvantages` reference, and the opening scene.
- `initial_authors_note.txt` — minimal turn-0 AN. The runtime extension overwrites this with a deterministic, state-derived AN on every turn.
- `<campaign_title_slug>.json` — the campaign lorebook. Constant entries the runtime reads:
  - `__pack_gm_overlay` (embedded pack overlay)
  - `__pack_complications` (pack universal + campaign-specific complications)
  - `__pack_reference` (pack vocabulary + a JSON header for the compatibility check)
  - `__campaign_bible` (premise / conflict / tone / thematic spine / antagonist)
  - `__campaign_truths` (JSON array of authored truths; `disable: true` so the GM never sees them — the extension picks one at a time as a director's note)
- `stages/*.json` — per-stage cache for resume / re-run: `premise`, `plot_skeleton`, `factions`, `npcs`, `locations`, `truths`, `complications`, `branches`, `sample_characters`.
- `stages/calls.jsonl` — every LLM call (request + response + usage).
- `stages/validation_log.txt` — schema retries, cross-stage warnings.
- `partials/*.partial.json` — incremental snapshots written as long stages (npcs, locations) progress; safe to delete after success.

`stages/npcs.json` includes a per-NPC `image_generation_prompt` field — a self-contained text-to-image prompt suitable for portrait generation. See [NPC Portraits](#npc-portraits) below.

If `--output` is omitted and `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` is set, the generator creates a campaign directory automatically (`<timestamp>_<pack>_<seed-stem>`).

If the target output directory already exists, the generator creates a sibling with a `_1`, `_2`, … suffix. To **resume an interrupted run** into the existing directory, pass `--resume`:

```bash
python -m campaign_generator \
    --genre symbaroum_dark_fantasy \
    --seed my_seed.yaml \
    --output ./campaigns/my_first_campaign/ \
    --resume
```

`--resume` reuses the cached `stages/*.json` and picks up at the first stage that has no cache entry.

## What the generator does NOT produce

These v1 outputs are retired:

- Node graphs (`nodes.json`), clue-edge graphs (`clue_chains.json`), Mermaid graph renders.
- Beat lists inside `plot_skeleton.json` — acts now carry only `title` and `goal`, plus a campaign-level `thematic_spine`.
- Spoiler dumps (`spoilers/full_campaign.md`, `spoilers/campaign_graph.*`). The campaign bible + truth set live in the lorebook; the player-facing player-knowledge section in `opening_hook.txt` covers the rest.
- A `pc_known_npcs.json` stage. Sample characters reference known NPCs via the cross-stage validator instead.

## Environment

- `OPENROUTER_API_KEY` is read from the repo-root `.env` if present.
- `OPENROUTER_MODEL` and `OPENROUTER_DRY_RUN_MODEL` override the model picked for live and `--dry-run` runs respectively.
- `CAMPAIGN_GENERATOR_GENRES_BASE_DIR` and `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` let `--genre <pack_name>` and bare `--output ./campaigns/...` resolve relative paths.

## Tests

```bash
cd campaign_generator
pytest
```

The current suite covers schema-level validation (`test_pack_validation.py`, `test_seed.py`, `test_seed_template.py`) and the NPC prompt's image-generation contract (`test_npc_prompt_contract.py`).

The full LLM-replay end-to-end test from v1 has been retired; its captured responses were v1-shaped and don't fit the new schema. A new replay fixture set needs to be captured against a real v2 run before that test can be restored — run the pipeline against the real LLM, copy `stages/*.json` into `tests/fixtures/canned_llm_responses/`, and re-author the test.

## NPC Portraits

A separate tool, [`image_generator/`](../image_generator/), reads `stages/npcs.json` after a campaign generation and renders portraits for each NPC. Pass `--with-images` to chain it after the campaign run, or invoke `image_generator` directly against the output directory.
