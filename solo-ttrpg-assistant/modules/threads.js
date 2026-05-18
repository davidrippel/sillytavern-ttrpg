// threads.js — open dramatic question CRUD.
//
// A thread is *what the player is chasing*. Threads are the v3 system's
// closest analogue to a quest log, but they are not waypoints. The
// extractor opens new threads when the player's prose introduces a new
// pursuit ("who killed Eda?") and advances or resolves them when the
// fiction does. The GM sees live threads in the AN as a reminder of
// what the player has been pulling on.

import { THREAD_LIMITS } from './constants.js';
import { ensureStoryStateShape, newThreadId, readStoryState, writeStoryState } from './util.js';

export const THREAD_STATUS = Object.freeze({
    live: 'live',
    escalating: 'escalating',
    resolved: 'resolved',
    retired: 'retired',
});

export async function openThread({ question, why = null, turn }) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const trimmed = String(question ?? '').trim();
    if (!trimmed) return null;
    const exists = state.threads.some(
        (t) => t.status !== THREAD_STATUS.retired && t.question.toLowerCase() === trimmed.toLowerCase(),
    );
    if (exists) return null;
    const thread = {
        id: newThreadId(),
        question: trimmed,
        status: THREAD_STATUS.live,
        openedTurn: Number.isFinite(turn) ? Number(turn) : state.turn,
        lastAdvancedTurn: Number.isFinite(turn) ? Number(turn) : state.turn,
        notes: why ? String(why) : '',
    };
    state.threads.push(thread);
    await writeStoryState(state);
    return thread;
}

export async function advanceThread(threadId, { status, why = null, turn } = {}) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const thread = state.threads.find((t) => t.id === threadId);
    if (!thread) return null;
    if (status && Object.values(THREAD_STATUS).includes(status)) {
        thread.status = status;
    }
    thread.lastAdvancedTurn = Number.isFinite(turn) ? Number(turn) : state.turn;
    if (why) thread.notes = String(why);
    await writeStoryState(state);
    return thread;
}

export async function retireThread(threadId) {
    return await advanceThread(threadId, { status: THREAD_STATUS.retired });
}

export async function renameThread(threadId, newQuestion) {
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const thread = state.threads.find((t) => t.id === threadId);
    if (!thread) return null;
    const trimmed = String(newQuestion ?? '').trim();
    if (trimmed) thread.question = trimmed;
    await writeStoryState(state);
    return thread;
}

/**
 * Threads visible to the GM in the AN: up to N live or escalating
 * threads, most-recently-advanced first.
 */
export function listLiveThreads(state, limit = THREAD_LIMITS.liveThreadsInAN) {
    const live = state.threads.filter(
        (t) => t.status === THREAD_STATUS.live || t.status === THREAD_STATUS.escalating,
    );
    live.sort((a, b) => Number(b.lastAdvancedTurn) - Number(a.lastAdvancedTurn));
    return live.slice(0, Math.max(1, Number(limit) || 3));
}

/**
 * All non-retired threads, for the threads-tray UI.
 */
export function listAllActiveThreads(state) {
    return state.threads.filter((t) => t.status !== THREAD_STATUS.retired);
}

/**
 * Find threads that haven't moved in `staleTurns` turns. The pacing
 * module uses this to decide when to emit a "lean in" pressure cue.
 */
export function listStaleThreads(state, staleTurns) {
    const cutoff = Number(state.turn) - Math.max(1, Number(staleTurns) || 5);
    return state.threads.filter(
        (t) => t.status === THREAD_STATUS.live && Number(t.lastAdvancedTurn) <= cutoff,
    );
}
