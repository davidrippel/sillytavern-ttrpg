# PROPOSAL: Node-based scenario design (replacing beats)

**Status:** design proposal — not a plan of record. Awaiting validation that the latest prompt patch hasn't already fixed the symptoms enough to defer this.

## Why we're here

Two pilots in, the same failure mode keeps reappearing: the LLM treats the beat list as a story to be told. It pushes toward the Current beat even when the player is roleplaying a moment. It closes scenes the player is still living in. It writes long because long is what novels do.

Prompt tweaks help at the margin. They don't fix the cause. As long as the AN says `Current beat: X / Next beat: Y`, the LLM has a salient nearby goal in its context window, and it will gravitate toward that goal. This is structural, not stylistic — you can't out-prompt gradient descent's preference for the most-rewarding nearby attractor.

The fix is the one Justin Alexander has been writing about for fifteen years: **don't prep plots, prep situations.**

Three of his pieces are the canon for this proposal:
- *Don't Prep Plots* — situations are circumstances; plots are sequences. Sequences create chokepoints. Situations don't.
- *The Three Clue Rule* — for any conclusion the player needs to reach, author at least three independent clues. Players miss the first, ignore the second, misread the third.
- *Node-Based Scenario Design* — replace the linear plot with a graph of nodes (locations, scenes, events, NPC encounters), connected by clues. Players move through the graph; they don't follow a path.

## The model

### Nodes (replace beats)

A **node** is a discrete situation: a location to investigate, an NPC to confront, an event that fires when conditions are met. Nodes are unordered — the player chooses which to engage when their clues point there.

Each node has:
- `id` (stable, e.g. `the_apartment`, `meet_rita`, `polaroid_burns`)
- `kind`: `location` | `npc_encounter` | `event`
- `description` (what's there, what happens if engaged, in prose)
- `entry_clues: [<clue_id>, ...]` — clues that, when discovered, point the player here
- `exit_clues: [<clue_id>, ...]` — clues this node provides on engagement (these point to other nodes)
- `gating: [<node_id>, ...]` — optional prerequisites; node is hidden until prereqs visited
- `triggers` — for `event` kind, conditions that fire it (turn count, NPC state, location reached)

Stored as new lorebook entries: `Node: <id>`, parallel to the existing `Clue: <id>` convention.

**Three-clue rule, hybrid enforcement:**
- **Authoring time:** the campaign generator targets ≥3 entry clues per node. The generator validates and warns when it can't.
- **Runtime:** the GM prompt allows the GM to *recombine* and *re-surface* existing clues if the player is stuck — but never to invent new canonical entities. "Reuse existing clues from new angles" rather than "invent new ones." This preserves the canon-strict rule while giving the GM safety margin.

### Clue graph (extend, don't replace)

The existing [clue_chains.js](../solo-ttrpg-assistant/modules/clue_chains.js) graph already supports `pointsTo`. Extend each clue with `pointsToNodes: [<node_id>, ...]` so a clue can point to one or more nodes (the inversion of the three-clue rule: many clues per conclusion).

`reachableClues()` already walks from discovered clues; extend it to also compute `reachableNodes` from discovered clues' `pointsToNodes`.

### NPC agendas (dynamic)

NPC lorebook entries declare initial agenda + scripted moves. Story state tracks what's happened:

```js
storyState.npcs = {
  [npc_id]: {
    attitude: 'wary' | 'friendly' | 'hostile' | ...,
    currentAction: 'searching the apartment' | null,
    secrets_revealed: ['secret_id', ...],
    last_seen_turn: 42,
  }
}
```

Mutated via `<<npc:NPC_ID:state:KEY=VALUE>>`. NPCs pursue their wants between scenes — when an NPC's `last_seen_turn` is stale, the GM is prompted to advance their agenda.

### Story state shape (additions)

```js
{
  // existing fields stay
  visitedNodes: [],          // ordered, for AN "Recently visited"
  completedNodes: [],        // node has been fully resolved
  npcs: { ... },             // see above
  // beats / pendingReveals can stay during transition; new campaigns won't use them
}
```

### Author's Note restructure

Drop:
- `Current beat`, `Next beat`, `Pending reveals`

Add:
- **Reachable nodes** — nodes whose entry clues the player has discovered, ungated, unresolved. Format: `- <id>: <one-line description>`.
- **Recently visited** — last 3 nodes, for context.
- **On-screen NPCs** — NPCs whose lorebook entry has fired in last N turns, with attitude + last action.

Keep:
- `Discovered clues`, `Available clues` (Available now ranks clues that point to reachable nodes higher), `Active threads`, `Recent beats` (rename to `Recent scenes`?), `Reminders`.

### GM prompt restructure

Remove from [07_GM_BASE_PROMPT.md](07_GM_BASE_PROMPT.md):
- "Run the authored adventure; don't improvise the overall story" — soften: "Run the authored situation; the story emerges from play."
- Sources of truth #3: "Current act (constant lorebook entry) — full beat list; drive toward them" — replace with "Current act — premise and stakes only; no scene sequence."
- The Current beat / Next beat AN entries from sources of truth #5.
- The entire Closure protocol's beat-resolution test — replaced by a node-resolution test.
- "Pending reveals" language.

Add:
- **The GM has no destination.** Reachable nodes are *available*, not *next*. The player chooses by acting on a clue, asking an NPC, going somewhere. Don't steer.
- **NPCs pursue their wants.** When the AN flags an NPC's last_seen_turn as stale, advance that NPC's agenda offscreen — they take an action, learn something, change attitude. Surface the consequences when the player reconnects.
- **Surface clues earned, not scheduled.** When the fiction earns it (search succeeds, NPC slips up, location yields evidence), tag `<<clue:found:ID>>`. The Three Clue Rule means it's fine to surface a clue the player wasn't actively looking for, if their action plausibly would have produced it.
- **Recombine, don't invent.** If the player is stuck and Available clues feels exhausted, re-surface a clue from a new angle — a different NPC mentions it, a re-examined location reveals more. Never invent a new named NPC, location, or clue.

### New closure tags

```
<<node:ID:visited>>             // player engaged with this node
<<node:ID:complete>>            // node is fully resolved
<<npc:ID:state:KEY=VALUE,...>>  // NPC state changed
```

`<<clue:found:ID>>` keeps working unchanged. `<<beat:...>>` and `<<act:...>>` deprecated for new campaigns; legacy code path retained for existing campaigns.

## Files affected

| File | Change |
| --- | --- |
| [solo-ttrpg-assistant/modules/plot_skeleton.js](../solo-ttrpg-assistant/modules/plot_skeleton.js) | Add node-loading parser; legacy beat code path stays for backward compat |
| `solo-ttrpg-assistant/modules/nodes.js` (new) | Parse `Node: <id>` entries; compute reachable nodes from discovered clues; mark visited/complete |
| [solo-ttrpg-assistant/modules/clue_chains.js](../solo-ttrpg-assistant/modules/clue_chains.js) | Add `pointsToNodes`; extend `reachableClues` to expose node mapping |
| [solo-ttrpg-assistant/modules/closure_tags.js](../solo-ttrpg-assistant/modules/closure_tags.js) | Add `node:visited`, `node:complete`, `npc:state` handlers; deprecate `beat:` for new campaigns |
| [solo-ttrpg-assistant/modules/authors_note.js](../solo-ttrpg-assistant/modules/authors_note.js) | New section renderers: Reachable nodes, Recently visited, On-screen NPCs |
| [solo-ttrpg-assistant/modules/constants.js](../solo-ttrpg-assistant/modules/constants.js) | Rewrite `AUTHORS_NOTE_SECTIONS` for node-mode |
| [solo-ttrpg-assistant/modules/util.js](../solo-ttrpg-assistant/modules/util.js) | Story state: add `visitedNodes`, `completedNodes`, `npcs`; bump `STORY_STATE_SCHEMA_VERSION` |
| [Docs/07_GM_BASE_PROMPT.md](07_GM_BASE_PROMPT.md) | Rewrite sources-of-truth, closure protocol, scene structure, pacing |
| `genres/*/...` campaign generator | Emit `Node: <id>` lorebook entries; enforce ≥3 entry-clues per node; emit NPC entries with explicit agenda fields |

## Open questions

1. **Mode flag.** New campaigns use node-mode; existing campaigns keep beat-mode. Set via a constant lorebook entry (e.g. `__campaign_mode: nodes` vs. `beats`)? Or detect by presence of `Node:` entries vs. `Act N:` entries? Probably the latter — implicit, no manual flagging needed.

2. **Pressure / failure-to-progress.** With no Current beat, no built-in tempo. Three options stack-ranked:
   - (a) NPC agendas as the pressure mechanism — each NPC has a `staleness_threshold` after which the GM advances their agenda offscreen.
   - (b) An optional `Tick: <turn_count>` event-node kind that fires regardless of player position.
   - (c) Overlay-defined "if no clue surfaced for N turns, GM may surface a recombined clue."
   Lean toward (a) + (c). Skip (b) unless playtests show wandering.

3. **Node-resolution test.** What does "complete" mean for a location node vs. an NPC encounter vs. an event? Probably node-kind-specific:
   - `location`: player has investigated and exit_clues have surfaced
   - `npc_encounter`: player has interacted and something changed (attitude, secret revealed, decision made)
   - `event`: player has experienced the consequence

4. **Migration.** Out of scope. New campaigns only. Beat-based campaigns continue using existing code path. The runtime branches on detected campaign mode.

5. **Generator-side three-clue enforcement.** What does the genre generator do when it can't find 3 plausible clue placements for a node? Options: warn and accept fewer; auto-generate filler clues from a template; mark the node as "underspecified" and skip it. Lean toward warn-and-accept with a flag in the lorebook so the runtime knows where to expect player to get stuck.

6. **Acts.** Do nodes span the campaign or per-act? Per-act with a campaign-level victory condition (a special node that gates the ending) is probably right. Acts dissolve into "node clusters with a gating boundary."

## Decision log

- 2026-05-08: Initial proposal — goals as primitives, dynamic NPC agendas.
- 2026-05-09: Reframed around the Alexandrian's node-based design after a second pilot showed prompt-only fixes don't address beat-drive. Three-clue rule chosen as hybrid (generator-targeted + runtime-recombination, no canon-invention).
- 2026-05-09: Node detection over explicit mode flag for backward compat.
