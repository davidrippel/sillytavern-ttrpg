# Agent Instructions

This file is auto-loaded by Claude Code, Codex, and other agent CLIs that respect the `AGENTS.md` convention. Read it before making changes.

## Documentation must stay in sync with code

Any code change in this repo must include corresponding documentation updates in the same change. This is a hard rule, not a suggestion — out-of-date docs are worse than no docs.

When you change code, update (or create) the relevant docs:

| If you change… | Also update… |
|---|---|
| `campaign_generator/` (pipeline, stages, schemas, CLI flags) | [`campaign_generator/README.md`](campaign_generator/README.md) and [`Docs/03_CAMPAIGN_GENERATOR_BRIEF.md`](Docs/03_CAMPAIGN_GENERATOR_BRIEF.md) |
| `image_generator/` (client, render, CLI) | [`image_generator/README.md`](image_generator/README.md) |
| `pack_generator/` | [`Docs/05_PACK_GENERATOR_BRIEF.md`](Docs/05_PACK_GENERATOR_BRIEF.md) and the pack generator's own README if present |
| `solo-ttrpg-assistant/` (SillyTavern extension) | [`Docs/04_EXTENSION_BRIEF.md`](Docs/04_EXTENSION_BRIEF.md) |
| Genre pack format / contract | [`Docs/02_GENRE_PACK_SPEC.md`](Docs/02_GENRE_PACK_SPEC.md) and [`Docs/06_PACK_AUTHORING_GUIDE.md`](Docs/06_PACK_AUTHORING_GUIDE.md) |
| Seed format / fields | [`Docs/09_SEED_FORMAT.md`](Docs/09_SEED_FORMAT.md) |
| GM base prompt behavior | [`Docs/07_GM_BASE_PROMPT.md`](Docs/07_GM_BASE_PROMPT.md) |
| New top-level component or tool | Add a row to the components inventory in [`Docs/01_SYSTEM_OVERVIEW.md`](Docs/01_SYSTEM_OVERVIEW.md) and create a sibling `README.md` for the tool |
| Env vars (added, removed, renamed) | [`.env.example`](.env.example) and any README that lists env vars |
| CLI flags (added, removed, renamed) | The relevant tool's README and brief |
| Output file layout | The "Outputs" or "Output files" section of the relevant README **and** the brief |

If a change genuinely doesn't need a doc update (e.g. internal refactor, comment fix, dependency bump that doesn't change behavior), say so explicitly in your final message ("no docs touched because: …"). Don't stay silent — the user is checking.

When creating a new top-level tool/package, it must ship with:
1. Its own `README.md` (purpose, prerequisites, env, usage, outputs).
2. A row in the components inventory in [`Docs/01_SYSTEM_OVERVIEW.md`](Docs/01_SYSTEM_OVERVIEW.md).
3. Cross-links from any related tool's README so users can find it.

## Style

- Match the existing README style: short Quickstart, env section, outputs section, manual verification steps where applicable.
- Use relative markdown links between docs (e.g. `[image_generator](../image_generator/README.md)`), not bare paths.
- Don't write speculative docs for code that doesn't exist yet.
