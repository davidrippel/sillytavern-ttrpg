import { AUTHORS_NOTE_KEYS, DEFAULT_SETTINGS, MODULE_NAME } from './constants.js';

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
    target.packs ??= {};
    target.logs ??= [];
    target.sheetInjection ??= structuredClone(DEFAULT_SETTINGS.sheetInjection);
    target.backup ??= structuredClone(DEFAULT_SETTINGS.backup);
    target.authorsNote ??= structuredClone(DEFAULT_SETTINGS.authorsNote);
    target.statusUpdate ??= structuredClone(DEFAULT_SETTINGS.statusUpdate);
    target.canonDetection ??= structuredClone(DEFAULT_SETTINGS.canonDetection);

    if (!target.activePack && target.activePackName && target.packs[target.activePackName]) {
        target.activePack = target.packs[target.activePackName];
    }

    return target;
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

export function formatSignedNumber(value) {
    const num = Number(value) || 0;
    return num > 0 ? `+${num}` : String(num);
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
    context.chatMetadata[AUTHORS_NOTE_KEYS.prompt] = String(text ?? '');
    await context.saveMetadata();
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
