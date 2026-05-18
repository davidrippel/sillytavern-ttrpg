// facts.js — fact ledger CRUD + lifecycle.
//
// A "fact" is a single declarative statement the GM's prose established
// in fiction: "Marek admitted he was at the docks the night Eda died."
// Facts are append-only and timestamped by `turn`. They move through a
// small lifecycle:
//
//   provisional  → just extracted from the latest GM message; not yet
//                  committed. Shown in an inline chip strip under the
//                  message with accept/edit/reject affordances.
//   accepted     → in-canon. Surfaced in the Recent facts AN section
//                  and used by the fact extractor as context.
//   rejected     → user marked the extraction wrong. Hidden from the
//                  AN, kept in the ledger for audit.
//
// The auto-commit policy promotes provisional → accepted after
// `factExtractor.autoCommitAfterTurns` turns of silence (default 0 —
// commit immediately at the end of the same turn so the AN is fresh
// before the next GM message). The chip strip still renders for the
// just-extracted facts via `listFactsForReview`, so the user can veto
// or edit even though commit already happened; chip clicks re-render
// the AN to reflect the change.

import { FACT_LIMITS } from './constants.js';
import { ensureStoryStateShape, newFactId, readStoryState, writeStoryState } from './util.js';

export const FACT_STATUS = Object.freeze({
    provisional: 'provisional',
    accepted: 'accepted',
    rejected: 'rejected',
});

/**
 * Append one or more proposed facts to the ledger as provisional entries.
 * The caller (fact_extractor) supplies `{ text, entities, sourceQuote }`
 * per fact; this function fills in id/turn/status.
 *
 * Returns the array of newly-created fact records.
 */
export async function appendProvisionalFacts(turn, drafts) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const created = [];
    const cap = Math.max(1, Number(FACT_LIMITS.maxFactsPerExtraction) || 5);
    for (const draft of (drafts ?? []).slice(0, cap)) {
        const text = String(draft?.text ?? '').trim();
        if (!text) continue;
        const fact = {
            id: newFactId(),
            turn: Number.isFinite(turn) ? Number(turn) : state.turn,
            text,
            entities: Array.isArray(draft.entities) ? draft.entities.slice(0, 8) : [],
            sourceQuote: String(draft?.sourceQuote ?? '').trim(),
            status: FACT_STATUS.provisional,
        };
        state.facts.push(fact);
        created.push(fact);
    }
    await writeStoryState(state);
    return created;
}

export async function acceptFact(factId) {
    return await transitionFact(factId, FACT_STATUS.accepted);
}

export async function rejectFact(factId) {
    return await transitionFact(factId, FACT_STATUS.rejected);
}

export async function editFact(factId, newText) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const fact = state.facts.find((f) => f.id === factId);
    if (!fact) return null;
    const trimmed = String(newText ?? '').trim();
    if (trimmed) {
        fact.text = trimmed;
        // Editing implicitly accepts the fact — the user is endorsing the
        // statement, just rephrased.
        fact.status = FACT_STATUS.accepted;
        fact.edited = true;
    }
    await writeStoryState(state);
    return fact;
}

async function transitionFact(factId, status) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const fact = state.facts.find((f) => f.id === factId);
    if (!fact) return null;
    fact.status = status;
    await writeStoryState(state);
    return fact;
}

/**
 * Auto-commit any provisional facts that are at least `cooldown` turns
 * old. Called at the top of every new assistant turn before extraction
 * runs — that way the AN reflects the previous turn's accepted facts and
 * the user's window to reject closed automatically.
 */
export async function autoCommitStaleProvisional(currentTurn, cooldown = 1) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    let mutated = false;
    for (const fact of state.facts) {
        if (fact.status === FACT_STATUS.provisional && currentTurn - Number(fact.turn) >= cooldown) {
            fact.status = FACT_STATUS.accepted;
            mutated = true;
        }
    }
    if (mutated) {
        await writeStoryState(state);
    }
    return mutated;
}

/**
 * The Recent facts AN section: the most recent N accepted facts in
 * chronological order. Provisional facts are excluded — they belong to
 * the inline chip strip, not the AN, until they auto-commit.
 */
export function listRecentAcceptedFacts(state, limit = FACT_LIMITS.recentFactsInAN) {
    return state.facts
        .filter((f) => f.status === FACT_STATUS.accepted)
        .slice(-Math.max(1, Number(limit) || 8));
}

/**
 * Facts that are still provisional at this exact moment — the set the
 * inline chip strip needs to render for the user.
 */
export function listProvisionalFacts(state) {
    return state.facts.filter((f) => f.status === FACT_STATUS.provisional);
}

/**
 * Facts extracted during the current turn that still warrant a chip in
 * the inline review strip. With auto-commit at cooldown 0, freshly
 * extracted facts flip to `accepted` before the chips render — so we
 * include any non-rejected fact tagged with the current turn, giving
 * the user a veto/edit window even though commit already happened.
 */
export function listFactsForReview(state) {
    const turn = Number(state.turn);
    return state.facts.filter(
        (f) => Number(f.turn) === turn && f.status !== FACT_STATUS.rejected,
    );
}

/**
 * Rewind: drop every fact established after `keepThroughTurn` regardless
 * of status. Cheap because facts are append-only and turn-tagged.
 *
 * Note: this also drops director's-note history and truthsRevealed entries
 * recorded after the cutoff, otherwise the pacing module would think
 * truths were already paid out.
 */
export async function rewindToTurn(keepThroughTurn) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const cutoff = Number(keepThroughTurn);
    state.facts = state.facts.filter((f) => Number(f.turn) <= cutoff);
    state.truthsRevealed = state.truthsRevealed.filter((t) => Number(t.turn) <= cutoff);
    if (Array.isArray(state.directorsNotes?.history)) {
        state.directorsNotes.history = state.directorsNotes.history.filter(
            (n) => Number(n.turn) <= cutoff,
        );
    }
    if (state.directorsNotes?.active && Number(state.directorsNotes.active.setTurn) > cutoff) {
        state.directorsNotes.active = null;
    }
    if (state.pressureCue && Number(state.pressureCue.setTurn) > cutoff) {
        state.pressureCue = { kind: null, reason: null, setTurn: 0 };
    }
    state.turn = Math.min(state.turn, cutoff);
    await writeStoryState(state);
    return state;
}
