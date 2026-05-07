# Campaign Generator

Python tool for generating a complete, pre-authored TTRPG campaign from a validated genre pack plus a campaign seed.

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

3. Create `.env` from the example and add your OpenRouter key. The `.env` lives at the **repo root** so it's shared with the pack generator.

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

6. Read `opening_hook.txt` and `initial_authors_note.txt`. Keep `spoilers/full_campaign.md` closed until after play.

If `CAMPAIGN_GENERATOR_GENRES_BASE_DIR` is set in `.env`, `--genre` can also be just the pack name:

```bash
python -m campaign_generator \
    --genre symbaroum_dark_fantasy \
    --seed my_seed.yaml
```

## Seed Template

Generate a blank annotated seed file:

```bash
python -m campaign_generator \
    --init-seed my_seed.yaml \
    --genre ../genres/symbaroum_dark_fantasy/
```

## Outputs

Successful runs write:

- `opening_hook.txt`
- `initial_authors_note.txt`
- `campaign_lorebook.json`
- `spoilers/full_campaign.md`
- `stages/*.json`
- `stages/calls.jsonl`
- `stages/validation_log.txt`

`stages/npcs.json` includes a per-NPC `image_generation_prompt` field — a self-contained text-to-image prompt suitable for portrait generation. See [NPC Portraits](#npc-portraits) below.

If `--output` is omitted and `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` is set, the generator creates a campaign directory automatically using:

- current timestamp
- pack name
- seed filename stem

Example: `20260421_153000_symbaroum_dark_fantasy_my_seed`

## Environment

- `OPENROUTER_API_KEY` is read automatically from `.env` if present.
- Default model comes from `CAMPAIGN_GENERATOR_DEFAULT_MODEL` in `.env`.
- `--dry-run` uses `CAMPAIGN_GENERATOR_DRY_RUN_MODEL` from `.env`.
- Default temperature comes from `CAMPAIGN_GENERATOR_DEFAULT_TEMPERATURE`.
- `CAMPAIGN_GENERATOR_GENRES_BASE_DIR` can provide the default root for `--genre`.
- `CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR` can provide the default root for generated campaign outputs.
- Optional transport/retry settings can also come from `.env`: `OPENROUTER_API_URL`, `OPENROUTER_TIMEOUT_SECONDS`, `OPENROUTER_MAX_RETRIES`, and `CAMPAIGN_GENERATOR_STAGE_MAX_RETRIES`.
- Image generation (used by `--with-images` and `python -m image_generator`): `IMAGE_GEN_MODEL` (required when rendering — no fallback), `IMAGE_GEN_DIMENSION` (default `1024`), `IMAGE_GEN_ASPECT_RATIO` (default `9:16`), `IMAGE_GEN_STYLE_OVERRIDE` (optional hard override for re-rendering an existing campaign in one consistent style).

## Naming Diversity

Each run picks a per-campaign **diversity seed** (a cultural/linguistic register, a secondary register, a district flavor, and a naming style) from the seed's `random_seed`, and scans up to the 5 most-recently-modified sibling campaigns under the campaigns base directory to build an **avoid list** of NPC and location names. Both are injected into the NPC and location prompts.

This keeps consecutive campaigns from converging on the same handful of attractor names ("Marcus", "Elias", "Anya", "Thorne", "The Velvet ___", "The Silk ___", etc.) and gives each campaign a more distinct cultural texture.

The cultural-register and district-flavor lists come from the pack's optional `naming.yaml` (see [Genre Pack Spec](../Docs/02_GENRE_PACK_SPEC.md#namingyaml-optional)). When a pack omits this file, the campaign generator falls back to a built-in cross-genre default list — fine for Earth-historical or fantasy-adjacent packs, but likely to misfire on hard-SF, weird-fiction, or strongly-coded fantasy packs (e.g. picking "Byzantine Greek with court titles" for a space opera). Pack authors should provide `naming.yaml` whenever the genre's naming conventions don't match the defaults; the [pack_generator](../pack_generator/README.md) emits it automatically.

To control it:

- Leave `random_seed` unset for a fresh register every run.
- Set `random_seed` in the seed YAML for reproducible naming.
- The avoid list is computed automatically from sibling campaign directories — no maintenance needed.
- Edit the pack's `naming.yaml` to change the available registers and district flavors for a given genre.

A progress message at the start of the NPC stage logs the chosen register and the size of the avoid list.

## Model Precedence

The effective model is resolved in this order:

1. `model:` in the seed YAML
2. `--model` on the CLI
3. `CAMPAIGN_GENERATOR_DRY_RUN_MODEL` when `--dry-run` is set
4. `CAMPAIGN_GENERATOR_DEFAULT_MODEL` from `.env`

## NPC Portraits

The NPC stage emits an `image_generation_prompt` for every NPC. Rendering those prompts into PNGs is a separate step handled by the [`image_generator`](../image_generator/README.md) tool, since image generation is slow and expensive and not every campaign needs portraits.

If you want the whole roster to share one look at generation time, add `image_style_hint` to the seed:

```yaml
image_style_hint: >
  Full-body photorealistic character portrait, realistic skin texture,
  natural anatomy, cinematic lighting. No illustration, comic,
  painting, or sketch look.
```

That hint is treated as a hard style requirement for every NPC portrait prompt in the roster.
Without a hint, the default prompt guidance now biases the roster toward full-body photorealistic portraits rather than sketch/comic/painting media.

Two ways to run it:

```bash
# Render portraits after generating a fresh campaign in one shot.
python -m campaign_generator \
    --genre symbaroum_dark_fantasy \
    --seed my_seed.yaml \
    --with-images

# Render (or re-render) portraits for an existing campaign directory.
# (Bare campaign names also work when CAMPAIGN_GENERATOR_CAMPAIGNS_BASE_DIR is set.)
python -m image_generator --campaign my_first_campaign

# Re-render an existing campaign in one photorealistic style without
# regenerating the campaign data.
python -m image_generator \
    --campaign my_first_campaign \
    --style-override "Full-body photorealistic character portrait, realistic skin texture, natural anatomy, cinematic lighting." \
    --overwrite
```

Required env (set in the repo-root `.env`):

```bash
IMAGE_GEN_MODEL=google/gemini-3-pro-image-preview
IMAGE_GEN_DIMENSION=1024
IMAGE_GEN_ASPECT_RATIO=9:16
IMAGE_GEN_STYLE_OVERRIDE=Full-body photorealistic character portrait, realistic skin texture, natural anatomy, cinematic lighting.
```

Portraits land in `<campaign_dir>/npc_images/<slug>.png`, with a manifest at `<campaign_dir>/npc_images/index.json`. See the [image_generator README](../image_generator/README.md) for full flag reference.

> Older campaigns generated before this feature was added will have empty `image_generation_prompt` fields. Re-run the NPC stage with `--stages npcs` to populate them, then run the image generator.

## Manual SillyTavern Verification

After generating a campaign, import `campaign_lorebook.json` into a fresh SillyTavern lorebook and confirm:

- The import succeeds without schema errors.
- `__pack_gm_overlay`, `__pack_failure_moves`, and `__pack_reference` are present.
- The player-facing files do not reveal antagonist secrets or late-act spoilers.
