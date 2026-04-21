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

3. Create `.env` from the example and add your OpenRouter key.

```bash
cp .env.example .env
```

4. Edit `my_seed.yaml`.
5. Run the generator:

```bash
python -m campaign_generator \
    --genre genres/symbaroum_dark_fantasy/ \
    --seed my_seed.yaml \
    --output ../campaigns/my_first_campaign/
```

6. Read `opening_hook.txt` and `initial_authors_note.txt`. Keep `spoilers/full_campaign.md` closed until after play.

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

## Environment

- `OPENROUTER_API_KEY` is read automatically from `.env` if present.
- Default model comes from `CAMPAIGN_GENERATOR_DEFAULT_MODEL` in `.env`.
- `--dry-run` uses `CAMPAIGN_GENERATOR_DRY_RUN_MODEL` from `.env`.
- Default temperature comes from `CAMPAIGN_GENERATOR_DEFAULT_TEMPERATURE`.
- Optional transport/retry settings can also come from `.env`: `OPENROUTER_API_URL`, `OPENROUTER_TIMEOUT_SECONDS`, `OPENROUTER_MAX_RETRIES`, and `CAMPAIGN_GENERATOR_STAGE_MAX_RETRIES`.

## Model Precedence

The effective model is resolved in this order:

1. `model:` in the seed YAML
2. `--model` on the CLI
3. `CAMPAIGN_GENERATOR_DRY_RUN_MODEL` when `--dry-run` is set
4. `CAMPAIGN_GENERATOR_DEFAULT_MODEL` from `.env`

## Manual SillyTavern Verification

After generating a campaign, import `campaign_lorebook.json` into a fresh SillyTavern lorebook and confirm:

- The import succeeds without schema errors.
- `__pack_gm_overlay`, `__pack_failure_moves`, and `__pack_reference` are present.
- The player-facing files do not reveal antagonist secrets or late-act spoilers.
