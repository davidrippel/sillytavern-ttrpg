# Example Pack: Symbaroum Dark Fantasy

The Symbaroum Dark Fantasy pack lives on disk at [`genres/symbaroum_dark_fantasy/`](../genres/symbaroum_dark_fantasy/). It is the canonical reference for what a valid **schema v2** pack (story-mode only — no attribute scores, no resource pools, no dice) looks like.

Earlier revisions of this document inlined every pack file under a long set of headings. That copy lived alongside the on-disk pack and inevitably drifted from it. The on-disk pack is now the single source of truth; this document is a pointer.

## How to read the pack

Open the directory and read the files in this order:

1. [`pack.yaml`](../genres/symbaroum_dark_fantasy/pack.yaml) — metadata, version, schema.
2. [`tone.md`](../genres/symbaroum_dark_fantasy/tone.md) — the mood the pack is reaching for. Read this first so the other files have context.
3. [`gm_prompt_overlay.md`](../genres/symbaroum_dark_fantasy/gm_prompt_overlay.md) — the genre-specific GM instructions. Embedded into every Symbaroum campaign's lorebook as `__pack_gm_overlay`.
4. [`complications.md`](../genres/symbaroum_dark_fantasy/complications.md) — the narrative complications the GM picks from when an action goes badly or the world pushes back. Embedded as `__pack_complications`.
5. [`advantages_disadvantages.md`](../genres/symbaroum_dark_fantasy/advantages_disadvantages.md) — the vocabulary of strengths and weaknesses a story-mode character is built from. Embedded as `__pack_reference`.
6. [`character_template.json`](../genres/symbaroum_dark_fantasy/character_template.json) — starting shape of a Symbaroum character sheet.
7. [`example_hooks.md`](../genres/symbaroum_dark_fantasy/example_hooks.md) — three opening hooks that demonstrate the tone in play.
8. [`generator_seed.yaml`](../genres/symbaroum_dark_fantasy/generator_seed.yaml) — defaults the campaign generator uses for Symbaroum runs.
9. [`naming.yaml`](../genres/symbaroum_dark_fantasy/naming.yaml) — naming registers and district flavors for the campaign generator's NPC and location stages.
10. [`REVIEW_CHECKLIST.md`](../genres/symbaroum_dark_fantasy/REVIEW_CHECKLIST.md) — QA items specific to this pack.

## Using it as a starting point for a new pack

To author a new pack by copying Symbaroum:

```bash
cp -r genres/symbaroum_dark_fantasy genres/<your_pack_name>
```

Then walk the file order above and rewrite each in turn. Edit `tone.md` and `gm_prompt_overlay.md` together — those are the two files where the genre's voice actually lives. The rest follow.

## Why this doc no longer inlines the pack

Two reasons:

1. **Drift.** Two copies of the same content (on disk and in this doc) always drift. The validator runs against the on-disk copy; this doc was decorative.
2. **Schema migration.** The pack format moved from v1 (stat-mode with attributes, resources, abilities) to v2 (story-mode only) in 2026-05. The on-disk pack is v2. Maintaining a v1 example here served no one — anyone reading this doc to learn the format would learn the wrong format.

For the formal contract every pack must satisfy, read [`02_GENRE_PACK_SPEC.md`](02_GENRE_PACK_SPEC.md). For conceptual guidance on writing one, read [`06_PACK_AUTHORING_GUIDE.md`](06_PACK_AUTHORING_GUIDE.md).
