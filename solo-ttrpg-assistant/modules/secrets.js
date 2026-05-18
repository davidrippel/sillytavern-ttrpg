// secrets.js — tier-2 lorebook unlocking.
//
// The campaign generator marks each per-NPC and per-location secret
// entry with `disabled: true`. This module enables a secret entry when
// the player has spent enough time on the underlying entity that
// surfacing the secret would land in fiction rather than feel like a
// dump.
//
// Triggering rules (deliberately simple, easy to tune):
//
//  - The player has accepted at least N facts that name the entity by
//    a keyword on the secret entry's key list.
//  - OR a thread is live that mentions the entity.
//
// The unlocked entry remains enabled for the rest of the campaign —
// once a secret is in scope, it's in scope. Re-locking is a manual
// operation via the Director panel.

import { loadAllLorebookEntries } from './lorebook_v2.js';
import { getContext } from './util.js';

const UNLOCK_AFTER_FACTS = 2;

/**
 * Walk every disabled lorebook entry tagged as secret and, for each,
 * check whether the entity it's secreting has accumulated enough
 * mentions to surface. Enable as appropriate; persist via the same
 * mechanism SillyTavern uses for world-info edits.
 *
 * Idempotent: an already-enabled entry is left alone.
 *
 * Returns the list of newly-enabled entry comments.
 */
export async function reevaluateSecretUnlocks(state) {
    const entries = await loadAllLorebookEntries();
    const unlocked = [];

    for (const entry of entries) {
        if (entry?.disable !== true && entry?.disabled !== true) continue;
        if (!isSecret(entry)) continue;

        const keys = collectKeys(entry);
        const mentions = countMentions(state, keys);
        const threadHit = anyThreadMentionsKeys(state, keys);

        if (mentions >= UNLOCK_AFTER_FACTS || threadHit) {
            const enabled = await enableEntry(entry);
            if (enabled) unlocked.push(entry.comment ?? entry.uid ?? '?');
        }
    }
    return unlocked;
}

function isSecret(entry) {
    if (entry?.secret === true) return true;
    const comment = String(entry?.comment ?? '').toLowerCase();
    if (comment.startsWith('secret:')) return true;
    if (comment.endsWith(' (secret)')) return true;
    return false;
}

function collectKeys(entry) {
    const out = new Set();
    const raw = entry?.key ?? entry?.keys ?? [];
    if (Array.isArray(raw)) {
        for (const k of raw) {
            const lower = String(k ?? '').toLowerCase().trim();
            if (lower) out.add(lower);
        }
    }
    return out;
}

function countMentions(state, keys) {
    if (keys.size === 0) return 0;
    let count = 0;
    for (const fact of state.facts ?? []) {
        if (fact.status !== 'accepted') continue;
        const hay = String(fact.text ?? '').toLowerCase();
        for (const key of keys) {
            if (hay.includes(key)) {
                count += 1;
                break;
            }
        }
    }
    return count;
}

function anyThreadMentionsKeys(state, keys) {
    if (keys.size === 0) return false;
    for (const thread of state.threads ?? []) {
        if (thread.status === 'retired' || thread.status === 'resolved') continue;
        const hay = String(thread.question ?? '').toLowerCase();
        for (const key of keys) {
            if (hay.includes(key)) return true;
        }
    }
    return false;
}

async function enableEntry(entry) {
    const context = getContext();
    if (typeof context.reloadEditor === 'function') {
        // Nothing to do — the live edit happens via the world-info API.
    }
    if (!entry || !entry._book) return false;
    try {
        if (typeof context.loadWorldInfo === 'function' && typeof context.saveWorldInfo === 'function') {
            const data = await context.loadWorldInfo(entry._book);
            const target = data?.entries?.[entry.uid];
            if (target) {
                target.disable = false;
                target.disabled = false;
                await context.saveWorldInfo(entry._book, data);
                return true;
            }
        }
    } catch {
        return false;
    }
    return false;
}
