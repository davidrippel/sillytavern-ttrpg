import {
    AUTHORS_NOTE_KEYS,
    DEFAULT_SETTINGS,
    MODULE_NAME,
    STORY_STATE_ARCHIVE_KEY,
    STORY_STATE_KEY,
    STORY_STATE_SCHEMA_VERSION,
} from './constants.js';

export function getContext() {
    return globalThis.SillyTavern.getContext();
}

export function getSettings() {
    const context = getContext();
    const settings = context.extensionSettings;

    if (!settings[MODULE_NAME]) {
        settings[MODULE_NAME] = structuredClone(DEFAULT_SETTINGS);
    }

    const target = settings[MODULE_NAME];
    if (!('enabled' in target)) {
        target.enabled = DEFAULT_SETTINGS.enabled;
    }
    target.packs ??= {};
    target.logs ??= [];
    target.sheetInjection ??= structuredClone(DEFAULT_SETTINGS.sheetInjection);
    target.backup ??= structuredClone(DEFAULT_SETTINGS.backup);
    target.authorsNote ??= structuredClone(DEFAULT_SETTINGS.authorsNote);
    target.factExtractor ??= structuredClone(DEFAULT_SETTINGS.factExtractor);
    target.ui ??= structuredClone(DEFAULT_SETTINGS.ui);
    target.characters ??= {};
    if (!('activeCharacterId' in target)) {
        target.activeCharacterId = null;
    }

    // Strip retired v1 settings keys quietly.
    delete target.statusUpdate;
    delete target.canonDetection;
    delete target.analyzer;

    if (!target.activePack && target.activePackName && target.packs[target.activePackName]) {
        target.activePack = target.packs[target.activePackName];
    }

    migrateLegacyCharacter(target);

    return target;
}

export function isExtensionEnabled() {
    return getSettings().enabled !== false;
}

function migrateLegacyCharacter(target) {
    if (!target.character || (target.characters && Object.keys(target.characters).length > 0)) {
        if (target.character) {
            delete target.character;
        }
        return;
    }

    const id = newCharacterId();
    const migrated = { ...target.character };
    migrated.id = id;
    migrated.packName ??= target.activePackName ?? null;
    migrated.personaKey ??= null;
    target.characters[id] = migrated;
    target.activeCharacterId = id;
    delete target.character;
}

export function getPowerUser() {
    return getContext().powerUserSettings ?? globalThis.power_user ?? null;
}

export function getPersonasMap() {
    return getPowerUser()?.personas ?? {};
}

let _personasModulePromise = null;
export async function getCurrentPersonaKey() {
    if (globalThis.user_avatar) {
        return globalThis.user_avatar;
    }
    if (!_personasModulePromise) {
        _personasModulePromise = import('../../../../personas.js').catch(() => null);
    }
    const mod = await _personasModulePromise;
    return mod?.user_avatar ?? null;
}

export function getCurrentPersonaKeySync() {
    return globalThis.user_avatar ?? null;
}

export function newCharacterId() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `char_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

export function newFactId() {
    return `f_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function newThreadId() {
    return `t_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function saveSettings() {
    getContext().saveSettingsDebounced();
}

export function escapeHtml(text) {
    return String(text ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

export function slugify(text) {
    return String(text ?? 'campaign')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '') || 'campaign';
}

export function timestampFilePart(date = new Date()) {
    const pad = (value) => String(value).padStart(2, '0');
    return [
        date.getFullYear(),
        pad(date.getMonth() + 1),
        pad(date.getDate()),
        '_',
        pad(date.getHours()),
        pad(date.getMinutes()),
        pad(date.getSeconds()),
    ].join('');
}

export function normalizeName(text) {
    return String(text ?? '').trim().toLowerCase();
}

export function safeJsonParse(text, fallback = null) {
    try {
        return JSON.parse(text);
    } catch {
        return fallback;
    }
}

export function readAuthorsNote() {
    const context = getContext();
    return String(context.chatMetadata?.[AUTHORS_NOTE_KEYS.prompt] ?? '');
}

export async function writeAuthorsNote(text) {
    const context = getContext();
    const value = String(text ?? '');
    context.chatMetadata[AUTHORS_NOTE_KEYS.prompt] = value;
    await context.saveMetadata();
    // ST's Author's Note drawer only re-reads `chat_metadata.note_prompt`
    // on CHAT_CHANGED, so a sidebar opened during this write would stay
    // stale. Sync the textarea DOM directly and fire 'input' so any
    // listeners (and ST's own autosize/persist plumbing) stay coherent.
    try {
        const $textarea = globalThis.jQuery?.('#extension_floating_prompt');
        if ($textarea?.length) {
            $textarea.val(value).trigger('input');
        }
    } catch {
        // best-effort UI sync
    }
}

// ---- Story state (v3 story-mode) ----------------------------------------

/**
 * The shape of `chatMetadata[solo_ttrpg_story_state]` in v3.
 *
 * facts[]      — append-only ledger of established facts. Each entry has
 *                `{ id, turn, text, entities, sourceQuote, status }`.
 *                `status` is one of:
 *                  - "provisional"  : just-extracted, not yet auto-accepted
 *                  - "accepted"     : in-canon, GM sees it in recent facts
 *                  - "rejected"     : user-rejected; kept for audit, hidden
 *                                     from the AN, may be re-extracted later.
 * threads[]    — open dramatic questions. Each entry has
 *                `{ id, question, status: live|escalating|resolved|retired,
 *                   lastAdvancedTurn, openedTurn, notes }`.
 * truthsRevealed[] — `{ truthId, turn, how }`. Tracks which of the
 *                campaign's authored truths the player now knows.
 * scene        — `{ location, presentNpcIds, tension, lastUpdatedTurn }`.
 * npcs         — `{ [id]: { lastSeenTurn, attitude, status } }`.
 *                Lightweight runtime state, derived by the fact extractor.
 * directorsNotes — `{ active: TruthRef|null, history[] }`. The pacing module
 *                writes to `active` when a campaign truth becomes
 *                reveal-eligible this scene.
 * pressureCue  — `{ kind: "lean-in"|"let-it-breathe"|"complication"|null,
 *                   reason, setTurn }`. The pacing module manages it.
 * turn         — monotonically increasing count of assistant messages.
 */
function defaultStoryState() {
    return {
        schemaVersion: STORY_STATE_SCHEMA_VERSION,
        facts: [],
        threads: [],
        truthsRevealed: [],
        scene: {
            location: null,
            presentNpcIds: [],
            tension: null,
            lastUpdatedTurn: 0,
        },
        npcs: {},
        directorsNotes: { active: null, history: [] },
        pressureCue: { kind: null, reason: null, setTurn: 0 },
        turn: 0,
    };
}

export function readStoryState() {
    const context = getContext();
    const stored = context.chatMetadata?.[STORY_STATE_KEY];
    if (!stored || typeof stored !== 'object') return null;
    return stored;
}

export async function writeStoryState(state) {
    const context = getContext();
    if (!context.chatMetadata) return;
    context.chatMetadata[STORY_STATE_KEY] = state;
    await context.saveMetadata();
}

/**
 * Normalise an in-memory state document to the v3 shape, filling in any
 * missing top-level keys. Does NOT migrate from older schema versions —
 * for that see `archiveAndResetLegacyStoryState`.
 */
export function ensureStoryStateShape(state) {
    const base = defaultStoryState();
    const merged = { ...base, ...(state ?? {}) };
    merged.facts = Array.isArray(merged.facts) ? merged.facts : [];
    merged.threads = Array.isArray(merged.threads) ? merged.threads : [];
    merged.truthsRevealed = Array.isArray(merged.truthsRevealed) ? merged.truthsRevealed : [];
    merged.scene = { ...base.scene, ...(merged.scene ?? {}) };
    merged.npcs = (merged.npcs && typeof merged.npcs === 'object') ? merged.npcs : {};
    merged.directorsNotes = { ...base.directorsNotes, ...(merged.directorsNotes ?? {}) };
    merged.directorsNotes.history = Array.isArray(merged.directorsNotes.history)
        ? merged.directorsNotes.history
        : [];
    merged.pressureCue = { ...base.pressureCue, ...(merged.pressureCue ?? {}) };
    merged.turn = Number.isFinite(merged.turn) ? Number(merged.turn) : 0;
    merged.schemaVersion = STORY_STATE_SCHEMA_VERSION;
    return merged;
}

export function freshStoryState() {
    return defaultStoryState();
}

/**
 * If chatMetadata contains a v1/v2 story state (beats/nodes/clues), move it
 * aside under `STORY_STATE_ARCHIVE_KEY` and reset the live key to a fresh
 * v3 document. Idempotent. Returns true if something was archived.
 */
export async function archiveAndResetLegacyStoryState() {
    const context = getContext();
    if (!context.chatMetadata) return false;
    const stored = context.chatMetadata[STORY_STATE_KEY];
    if (!stored || typeof stored !== 'object') return false;
    const version = Number(stored.schemaVersion);
    if (version === STORY_STATE_SCHEMA_VERSION) return false;

    const archive = context.chatMetadata[STORY_STATE_ARCHIVE_KEY] ?? [];
    archive.push({
        archivedAt: new Date().toISOString(),
        previousSchemaVersion: Number.isFinite(version) ? version : null,
        state: stored,
    });
    context.chatMetadata[STORY_STATE_ARCHIVE_KEY] = archive;
    context.chatMetadata[STORY_STATE_KEY] = defaultStoryState();
    await context.saveMetadata();
    return true;
}

export function getNoteDepth() {
    return Number(getContext().chatMetadata?.[AUTHORS_NOTE_KEYS.depth] ?? 4);
}

export function getNotePosition() {
    return Number(getContext().chatMetadata?.[AUTHORS_NOTE_KEYS.position] ?? 1);
}

export function getCurrentChatName() {
    const context = getContext();

    if (context.groupId) {
        return context.groups.find((group) => group.id === context.groupId)?.name ?? context.chatId ?? 'group_chat';
    }

    if (context.characterId !== undefined) {
        return context.characters[context.characterId]?.name ?? context.chatId ?? 'chat';
    }

    return context.chatId ?? 'chat';
}

export function deepClone(value) {
    return structuredClone(value);
}

export async function sha256Hex(text) {
    const input = typeof text === 'string' ? new TextEncoder().encode(text) : text;
    const digest = await crypto.subtle.digest('SHA-256', input);
    return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function setBusy($button, busyText) {
    const original = $button.data('solo-original-text') ?? $button.text();
    $button.data('solo-original-text', original);
    $button.prop('disabled', true).text(busyText);
}

export function clearBusy($button) {
    const original = $button.data('solo-original-text');
    $button.prop('disabled', false);
    if (original) {
        $button.text(original);
    }
}
