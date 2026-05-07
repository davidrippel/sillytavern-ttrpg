# Image Generator

Renders NPC portraits for a generated campaign by sending each NPC's `image_generation_prompt` (produced by the campaign generator's NPC stage) to an image-capable model on OpenRouter.

It is deliberately a separate tool from `campaign_generator`: image generation is slow and expensive, and not every campaign needs portraits. You can render a campaign immediately, days later, or never — and re-render at a different size without regenerating the campaign.

## Prerequisites

- A campaign directory previously produced by `python -m campaign_generator`. Specifically, `<campaign_dir>/stages/npcs.json` must exist and its NPCs must have non-empty `image_generation_prompt` fields. (Campaigns generated before this feature was added will have empty prompts; re-run that stage with `python -m campaign_generator --stages npcs ...` to populate them.)
- `OPENROUTER_API_KEY` set in the repo-root `.env`.
- `IMAGE_GEN_MODEL` set in the repo-root `.env`. **Required, no fallback.**

```bash
# .env
OPENROUTER_API_KEY=...
IMAGE_GEN_MODEL=google/gemini-3-pro-image-preview
IMAGE_GEN_DIMENSION=1024     # long-edge size in pixels (default: 1024)
IMAGE_GEN_ASPECT_RATIO=9:16  # W:H ratio (default: 9:16, portrait)
```

The short-edge dimension is derived from the long edge and the aspect ratio (e.g. `1024` + `9:16` → `576x1024`), then snapped to the nearest multiple of 8.

## Usage

### Standalone

```bash
python -m image_generator --campaign ./campaigns/my_first_campaign/
```

Flags:

- `--campaign PATH` (required) — directory of a generated campaign (must contain `stages/npcs.json`).
- `--model STR` — override `IMAGE_GEN_MODEL` for this run only.
- `--overwrite` — regenerate portraits even if the PNG file already exists. Without this, existing files are skipped, so repeated runs are cheap.
- `--only NAME[,NAME,...]` — render only the listed NPC names (matched exactly against `name` in `npcs.json`). Useful for re-rendering a single character.

### As part of a fresh campaign run

`campaign_generator` accepts a `--with-images` flag that calls the image generator after the rest of the pipeline finishes:

```bash
python -m campaign_generator \
    --genre symbaroum_dark_fantasy \
    --seed my_seed.yaml \
    --with-images
```

Image generation failures are logged but do **not** fail the campaign run — the campaign artifacts are produced regardless.

## Outputs

```
<campaign_dir>/
└── npc_images/
    ├── index.json         # name → { file, prompt, model, width, height, generated_at }
    ├── sister_valeria.png
    ├── foreman_bram.png
    └── ...
```

File names are slugified from each NPC's `name`. Collisions (rare) get `_2`, `_3`, etc. suffixes.

`index.json` is updated incrementally after each successful render, so a partial run leaves a usable manifest behind.

## Loading into SillyTavern

This iteration produces **plain PNGs** — no character-card metadata is embedded. Attach them in SillyTavern however you prefer (lorebook entry attachments, group chat avatars, expressions folder, manual character-card creation, etc.). A future iteration may automate this.

## Provider notes

The client targets OpenRouter's chat-completions endpoint with `modalities: ["image", "text"]` and decodes the base64 data URL the assistant returns. Any OpenRouter image-capable model that follows that response shape should work; `google/gemini-3-pro-image-preview` is the tested default. If you switch models, double-check the response shape — `client.py` has narrow extraction logic.
