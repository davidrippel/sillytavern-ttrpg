# Solo TTRPG Assistant — SillyTavern Extension Brief

A SillyTavern extension that runs the player-side state for a solo narrative campaign. **v3 (story-mode only).** The v1 stat/beat/node design described in earlier revisions of this brief is retired; see [`solo-ttrpg-assistant/CHANGELOG.md`](../solo-ttrpg-assistant/CHANGELOG.md) for the migration.

Hand this file to Claude Code along with [`01_SYSTEM_OVERVIEW.md`](01_SYSTEM_OVERVIEW.md), [`02_GENRE_PACK_SPEC.md`](02_GENRE_PACK_SPEC.md), and [`07_GM_BASE_PROMPT.md`](07_GM_BASE_PROMPT.md) for context.

---

## Goal

The extension keeps the story coherent across long chats by tracking what the GM's prose has *established in fiction*. It maintains:

- A ledger of **facts** (atomic statements, each carrying a verbatim source quote).
- A list of **threads** — open dramatic questions the player is pursuing.
- A small **scene context** (location, on-screen NPCs, tension).
- A record of which campaign **truths** the player has uncovered.
- A **pacing function** that nudges the GM (lean in / let it breathe / introduce a complication) and unlocks at most one campaign truth at a time as a "director's note".

Every state mutation is recoverable: the fact ledger is append-only, turn-tagged, and rewindable. The extension proposes; the user adjusts inline with one-click affordances.

---

## Tech stack

- JavaScript (ES modules), following the current SillyTavern extension template.
- SillyTavern's extension API, event system, and lorebook (`World Info`) API.
- Minimal external deps: a bundled YAML parser (`js-yaml` or equivalent) for `pack.yaml` / `generator_seed.yaml`; a bundled ZIP library (`jszip` or equivalent) for the backup/restore bundle.
- UI uses SillyTavern's CSS variables; the extension's own styles live in `style.css`.
- Persistent storage via `extension_settings[extensionName]` for settings and `chatMetadata` for per-chat story state.

---

## Pack loading

The extension reads the active genre pack at runtime. Only **schema v2** (story-mode) packs are accepted. Loading is via a directory-picker `<input type="file" webkitdirectory multiple>`.

The extension reads three files from disk:

- `pack.yaml` — metadata (display name, version, description). The compatibility check warns if the campaign's `__pack_reference` lorebook entry names a different pack.
- `character_template.json` — starting shape of the player character sheet.
- `advantages_disadvantages.md` — autocomplete suggestions for the sheet UI.

Three additional files reach the GM through the campaign lorebook (the campaign generator embeds them as constant entries) and the extension does not parse them at runtime:

- `__pack_gm_overlay` ← `gm_prompt_overlay.md`
- `__pack_complications` ← `complications.md`
- `__pack_reference` ← `advantages_disadvantages.md`

The remaining pack files (`tone.md`, `example_hooks.md`, `generator_seed.yaml`, `naming.yaml`, `REVIEW_CHECKLIST.md`) are consumed by the campaign generator, not the extension.

The pack loader explicitly rejects v1 files (`attributes.yaml`, `resources.yaml`, `abilities.yaml`, `failure_moves.md`) with a migration error pointing at [`02_GENRE_PACK_SPEC.md`](02_GENRE_PACK_SPEC.md).

---

## State model

`chatMetadata[solo_ttrpg_story_state]` (v3, `schemaVersion: 3`):

```
{
  schemaVersion: 3,
  facts: [{ id, turn, text, entities[], sourceQuote, status }],
  threads: [{ id, question, status, openedTurn, lastAdvancedTurn, notes }],
  truthsRevealed: [{ truthId, turn, how }],
  scene: { location, presentNpcIds[], tension, lastUpdatedTurn },
  npcs: { [id]: { lastSeenTurn, attitude, status } },
  directorsNotes: { active: {truthId,text,hint,setTurn} | null, history[] },
  pressureCue: { kind, reason, setTurn },
  turn
}
```

Fact lifecycle: `provisional` → (auto-commit after 1 turn) `accepted`, or → (user) `rejected`. Rejected facts stay in the ledger for audit but never reach the AN.

Thread lifecycle: `live` → `escalating` → `resolved`, or → `retired` (user action).

When the extension first sees a `chatMetadata` document with `schemaVersion` < 3 it moves the document aside under `solo_ttrpg_story_state_archive` and writes a fresh v3 document. The old state is preserved but not re-used; v1/v2 chats start over from turn 0 in v3.

---

## Per-turn pipeline

On every `MESSAGE_RECEIVED` for a non-user message:

1. **Auto-commit.** Provisional facts older than `factExtractor.autoCommitAfterTurns` (default 1) transition to `accepted`.
2. **Bump turn.** `state.turn += 1`.
3. **Fact extractor.** One LLM call (`generateRaw`) with the latest assistant prose, the previous player message (for context), recent accepted facts, live threads, scene context, and the campaign's authored truths (top 12). Returns:

```
{
  new_facts: [{ text, source_quote, entities }],
  thread_updates: [{ thread_id, status, why }],
  new_threads: [{ question, why }],
  truths_touched: [{ truth_id, how }],
  scene_delta: { location?, present_npc_ids?, tension? } | null,
  npc_state: [{ id, attitude, status }],
  notes: "..."
}
```

Each `source_quote` must appear verbatim in the prose (after smart-punct + whitespace normalisation). Facts that fail the check are dropped and logged.

4. **Apply diff.** New facts become provisional. Threads open / advance. Scene and NPC state update. Truths the prose touched are recorded if they match the active director's note.
5. **Pacing.** Compute pressure cue (`lean-in` / `let-it-breathe` / `complication` / null). Pick at most one campaign truth as the next director's note, based on adjacency to live threads and recent facts.
6. **Secrets.** Walk every disabled-by-default lorebook entry tagged `secret`; if enough accepted facts or threads name its keywords, enable it.
7. **AN rebuild.** Re-render the Author's Note from state.
8. **Inline UI.** Render fact chips under the new message; refresh the threads tray.

---

## Author's Note

Sections (in order, empty sections are omitted):

```
Thematic spine
Live threads
Recent facts
Scene context
On-screen NPCs
Director's notes
Pressure cue
Tone reminders
```

The AN never lists beat labels, node IDs, clue IDs, or "available clues / reachable nodes". The v2 navigational vocabulary is retired.

A final `Response length cap` line is appended to remind the GM of the base prompt's 1–2-paragraph default.

---

## Inline UI

Two pieces of UI live in the chat, not in the settings panel:

- **Fact chips.** Per-message strip rendered as `.solo-fact-chip` elements beneath the GM's `.mes_block`. Each chip shows one provisional fact with three buttons: ✓ accept, ✎ edit, ✗ reject. Untouched chips auto-accept on the next turn.
- **Threads tray.** A single `#solo-threads-tray` element prepended to the chat container. Each live thread is a chip; click to rename, × to retire, `+ thread` to open a new one.

Both are toggleable in the Director card.

---

## Settings panel

One flat panel; no nested submenus. Mounted into `#extensions_settings2`. Five collapsible `<details>` cards:

- **Campaign & Pack** — pack picker, load-pack directory input, backup export/import.
- **Character** — character CRUD, persona link, the in-panel sheet.
- **Story** — turn counter, live threads list, recent accepted facts, truths revealed, scene context, rewind-to-turn.
- **Director** — extractor toggle, inline-UI toggles, manual-fact entry, active director's note + pressure cue display, AN rebuild button.
- **Debug** — activity log and a state-dump button.

Nothing in the panel references attributes, abilities, resources, dice, or STATUS_UPDATE — those concepts are gone.

---

## Modules

```
solo-ttrpg-assistant/
├── manifest.json
├── style.css
├── index.js               — entry point + per-turn pipeline + persona events
├── settings.js            — flat settings panel driver
├── modules/
│   ├── constants.js       — module name, AN sections, settings shape
│   ├── util.js            — settings/state I/O, character/fact/thread IDs, helpers
│   ├── facts.js           — fact ledger CRUD + lifecycle + rewind
│   ├── facts_extractor.js — per-turn LLM extractor (replaces scene_analyzer.js)
│   ├── threads.js         — thread CRUD
│   ├── pacing.js          — pressure cue + director's-note selection
│   ├── lorebook_v2.js     — read-only lorebook helpers (truths, NPC names)
│   ├── secrets.js         — tier-2 lorebook unlock logic
│   ├── authors_note.js    — AN composition from state (no LLM summaries)
│   ├── inline_ui.js       — fact chips + threads tray (DOM injection)
│   ├── sheet.js           — v3 character-sheet UI + prompt-side rendering
│   ├── characters.js      — character CRUD (no mode field)
│   ├── pack.js            — v2 pack loader + lorebook helpers
│   ├── persona_link.js    — persona-to-character binding
│   ├── backup.js          — ZIP export/import
│   └── logger.js          — bounded activity log
└── ui/
    └── settings_panel.html
```

Modules deleted at the v2→v3 cut: `closure_tags.js`, `scene_analyzer.js`, `nodes.js`, `clue_chains.js`, `plot_skeleton.js`, `status_update.js`, `dice.js`.

---

## Settings document

`extension_settings[solo_ttrpg_assistant]`:

```
{
  enabled: true,
  packs: { [name]: <parsedPack> },
  activePackName: string | null,
  activePack: <parsedPack> | null,
  characters: { [id]: <characterRecord> },
  activeCharacterId: string | null,
  logs: [{ timestamp, level, message, details? }],
  sheetInjection: { enabled, fallbackDepth },
  backup: { autoExportMode },
  authorsNote: { recentFactsInAN, autoSummaryEvery },
  factExtractor: { enabled, autoCommitAfterTurns },
  ui: { inlineFactChips, threadsTray }
}
```

Retired keys (silently stripped on load): `statusUpdate`, `canonDetection`, `analyzer`.

---

## What gets sent to the GM

Per turn, the GM sees (assembled by SillyTavern from card + lorebook + AN + chat):

- **System prompt** (the v3 base prompt from [`07_GM_BASE_PROMPT.md`](07_GM_BASE_PROMPT.md)).
- **Constant lorebook entries**: `__pack_gm_overlay`, `__pack_complications`, `__pack_reference`, plus the campaign bible.
- **Keyword-triggered lorebook entries** that fire on the current context (NPCs, locations, factions, secrets that have been unlocked).
- The injected **character sheet** block (from `sheet.js → formatCharacterSheetForPrompt`).
- The **Author's Note** (the v3 sections above + a length-cap reminder).

What the GM never sees: campaign truths that the pacing system has not selected, secret lorebook entries that have not been unlocked, or any list-of-IDs scaffolding.

---

## Testing checklist

See [`solo-ttrpg-assistant/TESTING.md`](../solo-ttrpg-assistant/TESTING.md) for the full manual test pass. Categories:

- Setup + negative pack-load (v1 rejected with clear message).
- Character sheet round-trip (persists across reload).
- Per-turn pipeline (fact chips render; threads tray populates; AN reflects state).
- Provisional UX (accept / edit / reject behaviours).
- Quote validation (paraphrased facts are dropped).
- Rewind (facts after cutoff vanish; AN rebuilds).
- Pacing + director's notes (when a `__campaign_truths` entry is present).
- Backup export/import.
- Legacy-chat migration (v1/v2 state archived, v3 fresh).
- Disable / enable.
