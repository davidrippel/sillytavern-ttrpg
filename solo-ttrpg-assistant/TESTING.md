# Testing

v3 (story-mode) manual checks. Run these against a SillyTavern instance on `1.13.4` or newer with the OpenRouter (or any `generateRaw`-capable) connection bound.

## Setup

1. Enable the extension. Open the Extensions panel — confirm the `Solo TTRPG Assistant` flat panel renders with five collapsible cards.
2. Under **Campaign & Pack**, click `Load pack…` and pick `genres/symbaroum_dark_fantasy/`. The pack-info line should show the Symbaroum description; the active-pack label at the top should read `Pack: Symbaroum Dark Fantasy v2.0.0`.
3. **Negative check**: attempt to load a v1 pack (any with `attributes.yaml`). Confirm the loader raises a toastr error with a migration hint.

## Character sheet

1. Under **Character**, click `+ New`. Confirm the character select shows one entry and the sheet renders six fields: Name, Concept, Advantages, Disadvantages, Belongings, Relationships, Notes.
2. Add two advantages and one disadvantage. Save by tabbing out. Refresh the page — values persist.
3. Confirm the prompt-injected character sheet (visible via SillyTavern's prompt inspector) shows the story-mode block, not a stats block.

## Per-turn pipeline

1. Open a chat with the GM card whose system prompt is the v3 base prompt from `Docs/07_GM_BASE_PROMPT.md`.
2. Send a player message. Wait for the GM reply.
3. **Fact chips**: a strip of provisional fact chips renders under the GM message. Each chip has ✓ / ✎ / ✗.
4. **Threads tray**: the docked tray above the chat shows any threads the extractor opened.
5. **Story card**: the turn counter advances; recent facts appear under `Recent facts`; scene/NPC lines populate when the prose names them.
6. **Author's Note**: open SillyTavern's AN panel and confirm the rendered text uses the new sections (Thematic spine / Live threads / Recent facts / Scene context / On-screen NPCs / Director's notes / Pressure cue / Tone reminders) and ends with a `Response length cap` line.

## Provisional fact UX

1. After an extraction, click ✗ on one chip. The chip strikes through and fades. Confirm the rejected fact never enters the Story card's `Recent facts` list.
2. On another chip, click ✎ and edit the text. The chip dashes; the edited text appears in `Recent facts` after the next turn.
3. Leave a third chip untouched. Send the next player message. After the GM responds, the chip should have auto-accepted — `Recent facts` now contains it.

## Quote validation

1. Send a contrived message and inspect the activity log when the GM replies. Confirm that any fact whose `source_quote` does not appear in the prose is logged as `dropped fact with unverifiable quote: ...` and is NOT added to the ledger.

## Rewind

1. Use **Story → Rewind to turn…** with a turn number 2 below the current one.
2. Confirm: facts established after that turn vanish from the Story card; the threads tray loses any threads opened after that turn; the active director's note clears if it was set after the cutoff; the Author's Note rebuilds.

## Pacing & director's notes

1. (Requires a campaign whose lorebook contains a `__campaign_truths` constant entry with at least one truth.) Play several turns until a director's note appears in the AN.
2. Confirm the Director card shows the active note. After the GM lands it in prose, the note clears and `truths revealed` gains an entry.
3. After ~6 turns without a truth landing, confirm a `lean in` pressure cue appears.

## Backup

1. Run **Campaign & Pack → Export backup…**. Confirm a `.zip` downloads with `manifest.json`, `chat.jsonl`, `lorebook.json`, `authors_note.txt`, `character_sheet.json`, etc.
2. Open a fresh chat and run **Import backup…** with that ZIP. Confirm the chat, AN, and character restore.

## Legacy chat migration

1. Open a chat that was created under v0/v1 (with `chatMetadata.solo_ttrpg_story_state` carrying `currentBeatLabel` or `visitedNodes`).
2. Send any message. Confirm: a log entry "Archived v1/v2 story state and reset to v3." appears, the prior state is preserved under `chatMetadata.solo_ttrpg_story_state_archive`, and the Story card shows turn 0 with no facts/threads.

## Disable / enable

1. Toggle **Enabled** off. Send a player message; confirm the extractor does not run (no new entries in the activity log, no fact chips, no AN rebuild).
2. Toggle back on. Send another message; confirm normal operation resumes.
