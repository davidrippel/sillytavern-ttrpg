# Changelog

## 2.0.0 — Story-mode rebuild

The runtime is reworked around the v3 design described in [`Docs/04_EXTENSION_BRIEF.md`](../Docs/04_EXTENSION_BRIEF.md). Stat-mode, beat-mode, and node-mode are all retired; the system runs story-mode only.

**State model.** `chatMetadata[solo_ttrpg_story_state]` is bumped to `schemaVersion: 3` with a new shape:

```
{ facts[], threads[], truthsRevealed[], scene, npcs, directorsNotes,
  pressureCue, turn }
```

Existing v1/v2 state documents are auto-archived under `solo_ttrpg_story_state_archive` and replaced with a fresh v3 document on first chat-load. The old chat is not lost — it just resets the structured state tracker.

**Per-turn pipeline.** After each assistant message the extension now:

1. Auto-commits any provisional facts older than the cooldown.
2. Increments the turn counter.
3. Runs the **fact extractor** (replaces `scene_analyzer.js`) — one LLM call that returns new facts, thread updates, new threads, truths touched, scene delta, and NPC state. Each fact carries a `source_quote` that must appear verbatim in the GM prose (loose substring matching is gone).
4. Applies the extractor diff. New facts land as `provisional`; the inline chip strip surfaces them under the message with ✓ / ✎ / ✗ affordances.
5. Runs the pacing module — computes a pressure cue, selects at most one director's note from the campaign truths.
6. Reevaluates tier-2 secret lorebook entries (disabled-by-default NPC/location secrets enable when accumulated facts or threads brush their keys).
7. Rebuilds the Author's Note from state.
8. Refreshes inline UI.

**Author's Note vocabulary.** New section list:

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

Retired: `Current Act`, `Current beat`, `Next beat`, `Pending reveals`, `Discovered clues`, `Available clues`, `Reachable nodes`, `Recently visited`, `Recent beats`, `Recent scenes`, `Reminders`.

**Closure tags retired.** `<<beat:>>`, `<<clue:>>`, `<<node:>>`, and `<<npc:>>` are no longer parsed. The v3 GM base prompt forbids them.

**Inline UI.** Two new pieces of in-chat UI:

- Fact chip strip beneath each assistant message (`solo-fact-chip` elements with accept / edit / reject).
- Threads tray docked above the chat (`#solo-threads-tray`).

Both are toggleable from the Director card in the settings panel.

**Settings panel.** Full redesign — one flat panel with five collapsible cards (Campaign & Pack, Character, Story, Director, Debug). All v2 stats-mode UI (attribute roll buttons, ability rolls, resource bars, conditions, STATUS_UPDATE toggle, dice settings) removed.

**Character sheet.** v2 shape only:

```
{ name, concept, advantages[], disadvantages[], belongings[],
  relationships[{ name, tie }], notes }
```

No attributes, no abilities, no equipment-with-quantities, no resource pools.

**Pack loader.** Only schema-v2 (story-mode) packs are accepted. v1 packs (with `attributes.yaml`, `resources.yaml`, `abilities.yaml`, or `failure_moves.md`) raise a migration error pointing at `Docs/02_GENRE_PACK_SPEC.md`.

**Modules deleted.** `closure_tags.js`, `scene_analyzer.js`, `nodes.js`, `clue_chains.js`, `plot_skeleton.js`, `status_update.js`, `dice.js`.

**Modules added.** `facts.js`, `facts_extractor.js`, `threads.js`, `pacing.js`, `lorebook_v2.js`, `secrets.js`, `inline_ui.js`.

**Settings shape changes.** Retired keys (silently stripped on load): `statusUpdate`, `canonDetection`, `analyzer`. New keys: `factExtractor { enabled, autoCommitAfterTurns }`, `ui { inlineFactChips, threadsTray }`.

## 0.1.0

- Initial implementation covering tier 1 and tier 2 from `Docs/04_EXTENSION_BRIEF.md` (v1: stat-mode + beat-mode + node-mode).
