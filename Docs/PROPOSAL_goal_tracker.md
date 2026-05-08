# PROPOSAL: Goal/clue tracker (replacing or augmenting beats)

**Status:** design proposal — not a plan of record. Decision deferred until after the prompt-and-pending-reveals pass is validated by another pilot.

## Problem

Beats are linear and scripted. They encode *plot* (the sequence of authored scenes) rather than *progress* (what the player has learned, what NPCs are doing, what's still owed). In the pilot:

- The GM treated the beat list as a story to be told. Player movement between beats was scripted by the GM rather than earned by play.
- The clue graph already exists (`solo-ttrpg-assistant/modules/clue_chains.js`) but was never used. Clues weren't surfaced because the GM didn't need them — the next beat already told the GM where to go.
- "Beat skipping" is a symptom. The deeper issue is that beats are the wrong primitive for solo play, where the player should be discovering, not following.

The pending-reveals fix patches the symptom. This proposal addresses the cause.

## Proposed model

### Goals (replace beats)

Goals are an **unordered** list of "things the player needs to learn or accomplish" for the current act/campaign to complete. Each goal:

- `id` (stable, e.g. `learn_killer_identity`)
- `description` (what counts as completion, in prose)
- `clues: [<clue_id>, ...]` — clues that lead toward this goal
- Optional `gating: [<goal_id>, ...]` — prerequisite goals; gated goals are hidden until prerequisites complete

Stored as new lorebook entries: `Goal: <id>`, parallel to the existing `Clue: <id>` convention parsed by [clue_chains.js](../solo-ttrpg-assistant/modules/clue_chains.js).

Story state tracks `completedGoalIds: []` and (optionally) `goalProgressNotes: { [goal_id]: text }` for partial-progress notes the GM accumulates.

### NPC agendas (dynamic, in story state)

NPC lorebook entries declare *initial* agenda + scripted moves (authored by the campaign generator). Story state tracks *what's happened*. New `storyState.npcs` field, shaped per-NPC:

```js
{
  npc_id: {
    attitude: 'wary' | 'friendly' | 'hostile' | ...,   // current relational stance
    currentAction: 'searching the apartment' | null,    // what they're doing offscreen
    secrets_revealed: ['secret_id', ...],               // for spoiler tracking
    last_seen_turn: 42,                                 // freshness
  }
}
```

Mutated via a new closure tag: `<<npc:NPC_ID:state:KEY=VALUE>>`. Multiple keys per tag: `<<npc:rita:state:attitude=hostile,currentAction=fled>>`. Parsed alongside the existing `beat`/`clue`/`act` tags in [closure_tags.js](../solo-ttrpg-assistant/modules/closure_tags.js) (regex extension at line 16).

The AN renders an "On-screen NPCs" section listing each NPC whose lorebook entry has fired in the last N turns, with their current attitude and last action.

### Author's Note restructure

Replace:
- ~~Current beat~~
- ~~Next beat~~
- ~~Pending reveals~~

With:
- **Active goals** — open goals (those not in `completedGoalIds` and not gated out), formatted as `- <id>: <description>`
- **Recently completed goals** — last 3, for context
- **On-screen NPCs** — currently-fired NPCs with attitude + last action
- (keep) Discovered clues / Available clues / Active threads / Recent beats / Reminders

Constants: rewrite [AUTHORS_NOTE_SECTIONS](../solo-ttrpg-assistant/modules/constants.js) accordingly.

### GM prompt restructure

Remove from [07_GM_BASE_PROMPT.md](07_GM_BASE_PROMPT.md):
- "Run the authored adventure; don't improvise the overall story" (line 13–14) — soften
- "Current act (constant lorebook entry) — full beat list; drive toward them" (line 27)
- The entire **Closure protocol** beat-resolution test (lines 132–159) — replaced
- Pending reveals language (no longer needed)

Replace with:
- Active goals are destinations, not scenes. Don't narrate goal completion as a scripted event; let the player *earn* it through clue-following and NPC interaction.
- Surface a clue from Available clues when the fiction earns it — a search succeeds, an NPC slips up, a location yields evidence. Tag with `<<clue:found:ID>>`.
- A goal completes when the player has learned/done what its description requires. Tag with `<<goal:ID:complete>>`. Same resolution test (a/b/c/d) applies — the player must have actually contributed.
- NPCs pursue their agendas between scenes. When an NPC takes a meaningful action (changes attitude, moves location, acts on their want), update with `<<npc:ID:state:KEY=VALUE>>`.

### New closure tags

```
<<goal:ID:complete>>            // a goal was achieved this turn
<<npc:ID:state:KEY=VALUE,...>>  // NPC state changed
```

Existing `<<clue:found:ID>>` keeps working unchanged.

## Files affected

| File | Change |
| --- | --- |
| [solo-ttrpg-assistant/modules/plot_skeleton.js](../solo-ttrpg-assistant/modules/plot_skeleton.js) | Augment with goal-loading; or replace if beats are dropped entirely |
| [solo-ttrpg-assistant/modules/clue_chains.js](../solo-ttrpg-assistant/modules/clue_chains.js) | Add goal-aware clue ranking (clues pointing to active goals rank higher in Available clues) |
| [solo-ttrpg-assistant/modules/closure_tags.js](../solo-ttrpg-assistant/modules/closure_tags.js) | Extend regex; add `applyGoalComplete`, `applyNpcState` handlers |
| [solo-ttrpg-assistant/modules/authors_note.js](../solo-ttrpg-assistant/modules/authors_note.js) | New section renderers (Active goals, On-screen NPCs); drop beat sections |
| [solo-ttrpg-assistant/modules/constants.js](../solo-ttrpg-assistant/modules/constants.js) | Rewrite `AUTHORS_NOTE_SECTIONS` |
| [solo-ttrpg-assistant/modules/util.js](../solo-ttrpg-assistant/modules/util.js) | Story state shape: add `completedGoalIds`, `goalProgressNotes`, `npcs`; bump `STORY_STATE_SCHEMA_VERSION` |
| [Docs/07_GM_BASE_PROMPT.md](07_GM_BASE_PROMPT.md) | Rewrite sources-of-truth, closure protocol, scene structure |
| `genres/*/...` campaign generator | Emit `Goal: <id>` lorebook entries; emit NPC entries with explicit initial agenda fields |

## Open questions

1. **Failure-to-progress.** With no "current beat," there's no built-in pressure mechanism. If the player wanders for 20 turns, what escalates? Options: (a) GM-judged escalation per overlay, (b) a global "act timer" that ticks and triggers authored escalations, (c) NPC agendas naturally producing escalation (each NPC has a scheduled move that fires after N turns of no interaction). Lean toward (c) but it requires authoring discipline.

2. **GM escalation cues.** Should the AN include a "pressure" section listing NPCs whose `last_seen_turn` is stale (i.e. they've had time to act offscreen)? This would prompt the GM to advance NPC agendas without explicit player triggers.

3. **NPC tick mechanism.** Is NPC state purely event-driven (changes only when GM emits a tag), or does some background tick advance things? Event-driven is simpler and more predictable; tick-based handles "the killer is hunting you" pressure better. Probably event-driven, with overlay-defined "if NPC X hasn't been seen in N turns, they take action Y" rules.

4. **Migration.** Out of scope per user direction — new campaigns only. Existing beat-based campaigns continue using the current code path. The two systems can coexist by adding a campaign-level mode flag in the lorebook (e.g. a constant entry `__campaign_mode: goals` or `beats`).

5. **Closure-tag resolution test for goals.** The (a/b/c/d) test was tied to a single beat's central physical event. Goals are fuzzier ("learn the killer's identity" is a state, not an event). Need a goal-shaped resolution test — probably "the player has been told or has deduced it on-screen, with evidence in chat history."

6. **Multiple acts.** Do goals span the campaign, or per-act? If per-act, we need act transitions; if campaign-wide, acts may dissolve as a concept. Probably per-act, with a campaign-level "victory condition" goal that gates the ending.

## Decision log

- 2026-05-08: NPC agendas chosen as **dynamic, story-state-tracked** (not authored-only). User preference.
- 2026-05-08: No migration of existing beat-based campaigns. New mode applies to new campaigns only.
- 2026-05-08: Validate prompt + pending-reveals fix in another pilot before committing to this rewrite.
