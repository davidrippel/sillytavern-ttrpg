// pacing.js — pressure cues and director's-note gating.
//
// Where the v2 system used beats and acts to enforce dramatic shape,
// the v3 system uses a pacing function that watches the fact and thread
// ledger and nudges the GM with one of three short cues per turn:
//
//   "lean in"        — a live thread has been stale, or it's been a
//                      while since a truth landed. Raise stakes this
//                      scene.
//   "let it breathe" — a truth just landed; cooldown. Let the player
//                      sit with the consequences.
//   "complication"   — a complication from the pack is offered;
//                      weave it in.
//
// Director's-note unlocking lives here too. A campaign truth becomes
// reveal-eligible when (a) at least one live thread is "adjacent" to
// the truth, (b) the player has gathered enough adjacent facts (i.e.,
// the truth has been bumped by recent prose), and (c) the pacing
// function says it's time. Truths live outside the lorebook so the GM
// never sees them by accident — only the active director's note (and
// its history) ever reach the AN.

import { PACING } from './constants.js';
import { listStaleThreads, THREAD_STATUS } from './threads.js';

export const PRESSURE_KINDS = Object.freeze({
    leanIn: 'lean-in',
    letItBreathe: 'let-it-breathe',
    complication: 'complication',
});

/**
 * Compute the pressure cue for the current turn, without mutating state.
 * Callers (the AN composer) get back `{ kind, reason }` or
 * `{ kind: null }` if no cue applies.
 */
export function computePressureCue(state) {
    const turn = Number(state.turn) || 0;

    const lastTruthTurn = lastTurnAny(state.truthsRevealed);
    const cooldown = Math.max(1, Number(PACING.cooldownTurnsAfterTruth) || 2);
    if (lastTruthTurn !== null && turn - lastTruthTurn < cooldown) {
        return {
            kind: PRESSURE_KINDS.letItBreathe,
            reason: 'A campaign truth landed recently; let the consequences play out.',
        };
    }

    const stale = listStaleThreads(state, PACING.leanInAfterTurnsThreadStalled);
    if (stale.length > 0) {
        const longest = stale.reduce((acc, t) => (
            Number(t.lastAdvancedTurn) < Number(acc.lastAdvancedTurn) ? t : acc
        ), stale[0]);
        return {
            kind: PRESSURE_KINDS.leanIn,
            reason: `Thread "${longest.question}" hasn't advanced in several turns.`,
        };
    }

    const everLanded = state.truthsRevealed.length > 0;
    if (!everLanded && turn >= Number(PACING.leanInAfterTurnsWithoutTruth || 6)) {
        return {
            kind: PRESSURE_KINDS.leanIn,
            reason: 'No campaign truth has landed yet; raise stakes on a live thread.',
        };
    }

    return { kind: null, reason: null };
}

function lastTurnAny(entries) {
    if (!Array.isArray(entries) || entries.length === 0) return null;
    let max = -Infinity;
    for (const entry of entries) {
        const t = Number(entry?.turn);
        if (Number.isFinite(t) && t > max) max = t;
    }
    return Number.isFinite(max) ? max : null;
}

/**
 * Director's-note unlock: given the campaign's authored `truths`
 * (passed in by the caller — see lorebook_v2.js), pick at most one truth
 * to inject as a reveal-eligible director's note this turn.
 *
 * The selection rules are deliberately conservative:
 *
 *  - If `pressureCue.kind === 'let-it-breathe'`, return null (don't pile on).
 *  - If an active director's note from a previous turn was NOT used by
 *    the GM (i.e., no fact in `truthsRevealed` for it yet), prefer
 *    holding it for one more scene rather than rotating.
 *  - Otherwise, pick a truth whose "adjacency keys" overlap with the
 *    questions of live threads — preferring truths that the player's
 *    recent facts already brushed against.
 *
 * Returns `{ truthId, hint, why }` or null.
 */
export function selectDirectorsNote({ state, pressureCue, truths, liveThreads, recentFacts }) {
    if (!Array.isArray(truths) || truths.length === 0) return null;
    if (pressureCue?.kind === PRESSURE_KINDS.letItBreathe) return null;

    // Honor a still-live note that the GM hasn't paid out yet.
    const active = state.directorsNotes?.active;
    if (active && !state.truthsRevealed.some((t) => t.truthId === active.truthId)) {
        return active;
    }

    const revealedIds = new Set(state.truthsRevealed.map((t) => t.truthId));
    const candidates = truths.filter((t) => !revealedIds.has(t.id));
    if (candidates.length === 0) return null;

    const threadQuestionTokens = liveThreads
        .flatMap((t) => tokenize(t.question))
        .filter(Boolean);
    const recentTokens = recentFacts
        .flatMap((f) => tokenize(f.text))
        .filter(Boolean);
    const haystackThread = new Set(threadQuestionTokens);
    const haystackRecent = new Set(recentTokens);

    const scored = candidates.map((truth) => {
        const truthTokens = tokenize(truth.text);
        let score = 0;
        for (const tok of truthTokens) {
            if (haystackThread.has(tok)) score += 2;
            if (haystackRecent.has(tok)) score += 1;
        }
        if (Array.isArray(truth.adjacencyKeys)) {
            for (const key of truth.adjacencyKeys) {
                if (haystackThread.has(String(key).toLowerCase())) score += 3;
                if (haystackRecent.has(String(key).toLowerCase())) score += 2;
            }
        }
        return { truth, score };
    });

    scored.sort((a, b) => b.score - a.score);
    const top = scored[0];
    if (!top || top.score === 0) return null;

    return {
        truthId: top.truth.id,
        hint: top.truth.hint ?? null,
        text: top.truth.text,
        why: 'Adjacent to a live thread or recently-established facts.',
        setTurn: state.turn,
    };
}

function tokenize(text) {
    return String(text ?? '')
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter((tok) => tok.length >= 3);
}
