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
import { log } from './logger.js';

const TRUTHS_ENTRY_COMMENT = '__campaign_truths';

function _collectChatLorebookName(context) {
    const metadata = context.chatMetadata ?? {};
    const candidates = [
        metadata.world_info,
        metadata.world,
        metadata.chat_world,
        metadata.chat_lore,
        metadata.worldInfo,
    ];
    for (const candidate of candidates) {
        if (typeof candidate === 'string' && candidate.trim()) return candidate;
        if (candidate && typeof candidate === 'object') {
            for (const key of ['name', 'world', 'selected']) {
                if (typeof candidate[key] === 'string' && candidate[key].trim()) return candidate[key];
            }
        }
    }
    return null;
}

function _collectCharacterLorebookName(context) {
    try {
        const id = context.characterId;
        if (id == null) return null;
        const character = context.characters?.[id];
        if (!character) return null;
        const candidates = [
            character.data?.extensions?.world,
            character.data?.character_book?.name,
            character.character_book?.name,
            character.world,
        ];
        for (const candidate of candidates) {
            if (typeof candidate === 'string' && candidate.trim()) return candidate;
        }
    } catch {
        // best-effort
    }
    return null;
}

function _collectGlobalLorebookNames() {
    const names = new Set();
    // `selected_world_info` is the runtime array of currently-active book
    // names. `world_names` is the master list of every world-info file
    // SillyTavern knows about — we include it so the lookup works even
    // when the user has only opened the book in the editor without
    // marking it active.
    const sources = [
        globalThis.selected_world_info,
        globalThis.world_names,
        globalThis.world_info?.globalSelect,
        globalThis.world_info?.charLore,
    ];
    for (const source of sources) {
        if (Array.isArray(source)) {
            for (const name of source) {
                if (typeof name === 'string' && name.trim()) names.add(name);
            }
        }
    }
    return [...names];
}

/**
 * Load every entry from every world-info book reachable from the current
 * chat. Checks (in order, de-duplicated by name):
 *
 *   1. `context.getCharaLoreBooks()` — character-bound books.
 *   2. The chat-bound book name (chatMetadata.world_info etc).
 *   3. The character card's `character_book.name` / `data.extensions.world`.
 *   4. SillyTavern globals: `selected_world_info` (active set),
 *      `world_names` (master list), and `world_info.globalSelect` /
 *      `world_info.charLore`.
 *
 * Walking the master list (`world_names`) means the lookup succeeds as
 * long as the user has the lorebook loaded anywhere in SillyTavern —
 * they don't have to bind it to character or chat first. Returns `[]`
 * if SillyTavern's world-info API isn't available yet.
 */
export async function loadAllLorebookEntries() {
    const context = getContext();
    if (typeof context.loadWorldInfo !== 'function') return [];

    const names = new Set();
    try {
        if (typeof context.getCharaLoreBooks === 'function') {
            const books = (await context.getCharaLoreBooks()) ?? [];
            for (const name of books) {
                if (typeof name === 'string' && name.trim()) names.add(name);
            }
        }
    } catch {
        // best-effort
    }

    const chatName = _collectChatLorebookName(context);
    if (chatName) names.add(chatName);

    const charName = _collectCharacterLorebookName(context);
    if (charName) names.add(charName);

    for (const name of _collectGlobalLorebookNames()) {
        names.add(name);
    }

    console.debug('[solo-ttrpg] loadAllLorebookEntries — candidate books:', [...names]);
    if (names.size === 0) {
        console.warn('[solo-ttrpg] No lorebook book names discoverable from context/globals.');
        return [];
    }

    const all = [];
    for (const name of names) {
        try {
            const data = await context.loadWorldInfo(name);
            const count = data?.entries ? Object.keys(data.entries).length : 0;
            console.debug(`[solo-ttrpg] Loaded "${name}" — ${count} entries.`);
            if (data?.entries) {
                for (const id of Object.keys(data.entries)) {
                    all.push({ ...data.entries[id], _book: name });
                }
            }
        } catch (error) {
            console.warn(`[solo-ttrpg] Failed to load world info "${name}":`, error);
            log(`Failed to load world info "${name}".`, 'warn', error?.message);
        }
    }
    return all;
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
