// lorebook_v2.js — read-only helpers over the active chat's lorebook
// (SillyTavern "World Info"). The campaign generator produces the
// lorebook for a campaign with three tiers of content:
//
//   Tier 1 — public entries (NPCs, locations, factions). Always
//            enabled, fire on keyword in context.
//   Tier 2 — secret entries (per-NPC / per-location). Generated
//            with `disabled: true`; the extension enables them
//            when triggering facts/threads accumulate. See secrets.js.
//   Tier 3 — campaign truths. NOT in the lorebook. Stored in a
//            constant entry named `__campaign_truths` (a JSON
//            payload), invisible to the GM. The pacing module
//            picks one at a time and injects it into the AN as a
//            director's note.
//
// This module exposes minimal readers; mutations live in secrets.js.

import { PACK_LOREBOOK_ENTRIES } from './constants.js';
import { getContext, safeJsonParse } from './util.js';

const TRUTHS_ENTRY_COMMENT = '__campaign_truths';

/**
 * Load every entry from every world-info book attached to the current chat.
 * Returns `[]` if SillyTavern's world-info API isn't available yet.
 */
export async function loadAllLorebookEntries() {
    const context = getContext();
    const wi = context.worldInfo ?? globalThis.worldInfoData ?? null;
    if (!wi) return [];

    try {
        // SillyTavern exposes a `getCharaLoreBooks()` + `loadWorldInfo()`
        // pair on context. We accept either shape and fall back to a
        // global if neither is available.
        if (typeof context.getCharaLoreBooks === 'function' && typeof context.loadWorldInfo === 'function') {
            const books = (await context.getCharaLoreBooks?.()) ?? [];
            const all = [];
            for (const name of books) {
                const data = await context.loadWorldInfo(name);
                if (data?.entries) {
                    for (const id of Object.keys(data.entries)) {
                        all.push({ ...data.entries[id], _book: name });
                    }
                }
            }
            return all;
        }
    } catch {
        // Fall through.
    }

    return [];
}

/**
 * Find a single lorebook entry by exact `comment` (the field the
 * campaign generator uses to name constant entries like
 * `__pack_gm_overlay` or `__campaign_truths`).
 */
export async function findLorebookEntryByComment(comment) {
    const entries = await loadAllLorebookEntries();
    return entries.find((e) => String(e.comment ?? '').trim() === comment) ?? null;
}

/**
 * Load the campaign's authored truth set from the special constant
 * lorebook entry. The entry's content is a JSON array of `{ id, text,
 * hint, adjacencyKeys[] }` objects. The entry should be marked
 * `prevent_recursion: true` so the GM never sees it directly — only
 * the director's-note system reads it.
 *
 * Returns `[]` if the campaign generator hasn't shipped a truths entry
 * yet. The pacing module degrades gracefully.
 */
export async function loadCampaignTruths() {
    const entry = await findLorebookEntryByComment(TRUTHS_ENTRY_COMMENT);
    if (!entry?.content) return [];
    const parsed = safeJsonParse(entry.content, null);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((t) => t && typeof t === 'object' && t.id && t.text);
}

/**
 * Resolve a friendly display name for an NPC ID by looking at lorebook
 * entries flagged as NPC entries. Returns the comment/key as a
 * fallback. Used by the AN composer to render `On-screen NPCs`.
 */
export async function resolveNpcName(npcId) {
    if (!npcId) return null;
    const entries = await loadAllLorebookEntries();
    const match = entries.find((e) => {
        const comment = String(e.comment ?? '');
        if (comment === `NPC: ${npcId}` || comment === npcId) return true;
        const keys = e.key ?? e.keys ?? [];
        return Array.isArray(keys) && keys.some((k) => String(k).toLowerCase() === String(npcId).toLowerCase());
    });
    return match?.comment?.replace(/^NPC:\s*/, '') ?? String(npcId);
}

export const PACK_ENTRY_NAMES = PACK_LOREBOOK_ENTRIES;
