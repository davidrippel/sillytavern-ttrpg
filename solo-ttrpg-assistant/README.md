# Solo TTRPG Assistant

SillyTavern extension for solo narrative campaigns. **Version 3 (story-mode only.)**

The runtime tracks the unfolding story as a stream of *facts* and *threads* — atomic statements the GM's prose established, and open dramatic questions the player is pursuing. After each assistant message, a fact extractor reads the prose and proposes new facts (with verbatim source quotes), thread updates, scene context, and any campaign truths the prose touched. The Author's Note is then rebuilt deterministically from this state, so what the GM sees on every turn is the *current dramatic situation*, never a checklist of beats or nodes.

The v2 system (stats mode, beats, nodes, clue chains, closure tags) is retired. See `CHANGELOG.md` for the migration.

## Install

1. Copy `solo-ttrpg-assistant/` into your SillyTavern extensions directory.
2. Enable the extension in SillyTavern.
3. Open the extension drawer in the Extensions panel.
4. Under **Campaign & Pack**, click `Load pack…` and choose a v2 pack directory (e.g. `genres/symbaroum_dark_fantasy/`).

## Author's Note settings (recommended)

For prompt-cache friendliness — the Author's Note changes every turn, so its placement determines how much of the prompt gets re-billed on each request — set in the Author's Note panel:

- **Position:** `In-chat @ Depth`
- **Depth:** `4`
- **Role:** `System`
- **Frequency:** `1`

The extension's injected character sheet rides the same depth. System prompt, genre overlay, constant lorebook entries, and older chat history stay in the cache prefix; only the last few messages are uncached. See `Docs/07_GM_BASE_PROMPT.md` for the full rationale.

## Settings panel

One flat panel, no submenus, five collapsible cards:

- **Campaign & Pack** — load a v2 pack directory, switch between loaded packs, export / import the backup bundle.
- **Character** — story-mode sheet: name, concept, advantages, disadvantages, belongings, relationships. No attribute scores, abilities, or resource pools.
- **Story** — the live state: turn counter, live threads, recent accepted facts, truths revealed, current scene. One-click rewind to a previous turn.
- **Director** — toggle the fact extractor and the inline UI, manually add a fact the extractor missed, view the active director's note and pressure cue, force an Author's Note rebuild.
- **Debug** — activity log and a state-dump button.

## Inline UI

Two pieces of UI live *in the chat* rather than in the settings panel — so normal play is zero-click:

- **Fact chips.** After every assistant message, the extractor's proposed facts render as a chip strip below the message. Each chip has ✓ accept / ✎ edit / ✗ reject. Chips auto-accept after the next assistant message if untouched.
- **Threads tray.** A single docked row above the chat shows live threads. Click to rename, × to retire, `+ thread` to open a new one manually.

Both are toggleable from the Director card.

## What gets sent to the GM

On every turn the GM sees (via the Author's Note and lorebook):

- A short **Thematic spine** reminder pulled from the campaign bible.
- Up to three **Live threads** — what the player is currently chasing.
- The last few **Recent facts** the prose established.
- A line of **Scene context** (location, tension).
- The **On-screen NPCs** with their tracked attitudes.
- At most one **Director's note** — a single campaign truth the pacing system has marked reveal-eligible. The GM is allowed to reveal *only* this truth; the rest of the campaign's underlying answers stay hidden.
- An optional **Pressure cue**: "lean in", "let it breathe", or "introduce a complication".
- A short pointer to the genre overlay (`__pack_gm_overlay`), which reaches the GM through the lorebook.

What the GM never sees: lists of beat labels, node IDs, clue IDs, "available clues", or "reachable nodes". The v2 navigational vocabulary is retired.

## Pack requirements (v2)

The extension only loads schema-v2 (story-mode) packs. Required files:

```
pack.yaml
character_template.json
gm_prompt_overlay.md
tone.md
complications.md
advantages_disadvantages.md
example_hooks.md
generator_seed.yaml
```

If a v1 pack (with `attributes.yaml`, `resources.yaml`, `abilities.yaml`, or `failure_moves.md`) is loaded, the pack loader raises a migration error pointing at `Docs/02_GENRE_PACK_SPEC.md`.

## Closure tags are retired

Earlier versions of the GM prompt asked the GM to emit `<<beat:..>>`, `<<clue:..>>`, `<<node:..>>`, or `<<npc:..>>` tags at the end of messages. The v3 base prompt explicitly forbids them; the extension has no parser to consume them anyway. If they ever appear in prose, they pass through to the user as visible text — fix the base prompt rather than the extension.
