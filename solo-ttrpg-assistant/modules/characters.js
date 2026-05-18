// characters.js — character CRUD (v3, story-mode only).
//
// In v2 the system carried two character "modes" (`pack` for stat-mode,
// `story` for story-mode) with a runtime converter between them. v3
// retires stat-mode entirely; every character uses the v2 character
// template shape (name, concept, advantages, disadvantages, belongings,
// relationships, notes). There is no mode field anymore.

import { getActivePack, initializeCharacterForPack } from './pack.js';
import { log } from './logger.js';
import {
    getContext,
    getCurrentPersonaKey,
    getPersonasMap,
    getSettings,
    newCharacterId,
    saveSettings,
} from './util.js';

const characterSubscribers = new Set();
const characterMetaSubscribers = new Set();
let suppressPersonaSync = false;

function emitCharactersChanged() {
    for (const listener of characterSubscribers) listener();
}

export function subscribeCharacters(listener) {
    characterSubscribers.add(listener);
    return () => characterSubscribers.delete(listener);
}

export function emitCharacterMetaChanged() {
    for (const listener of characterMetaSubscribers) listener();
}

export function subscribeCharacterMeta(listener) {
    characterMetaSubscribers.add(listener);
    return () => characterMetaSubscribers.delete(listener);
}

export function listCharacters() {
    const settings = getSettings();
    return Object.values(settings.characters ?? {});
}

export function getCharacterById(id) {
    return getSettings().characters?.[id] ?? null;
}

export function getActiveCharacterId() {
    return getSettings().activeCharacterId ?? null;
}

export function getActiveCharacter() {
    const settings = getSettings();
    const id = settings.activeCharacterId;
    if (id && settings.characters?.[id]) {
        return settings.characters[id];
    }
    const first = Object.values(settings.characters ?? {})[0];
    if (first) {
        settings.activeCharacterId = first.id;
        return first;
    }
    return null;
}

export function ensureActiveCharacter() {
    const existing = getActiveCharacter();
    if (existing) return existing;
    return createCharacter({ name: '' });
}

function buildCharacterRecord({ name = '', packName = null, personaKey = null } = {}) {
    const settings = getSettings();
    const pack = settings.packs?.[packName] ?? getActivePack();
    const base = initializeCharacterForPack(pack);
    return {
        ...base,
        id: newCharacterId(),
        name: name || base.name || '',
        packName: packName ?? settings.activePackName ?? null,
        personaKey: personaKey ?? null,
    };
}

export function createCharacter(options = {}) {
    const settings = getSettings();
    const record = buildCharacterRecord(options);
    settings.characters[record.id] = record;
    settings.activeCharacterId = record.id;
    saveSettings();
    log(`Created character ${record.name || '(unnamed)'}.`);
    emitCharactersChanged();
    return record;
}

export function duplicateCharacter(id) {
    const source = getCharacterById(id);
    if (!source) throw new Error(`Unknown character "${id}".`);
    const settings = getSettings();
    const copy = {
        ...JSON.parse(JSON.stringify(source)),
        id: newCharacterId(),
        name: `${source.name || 'Unnamed'} (copy)`,
        personaKey: null,
    };
    settings.characters[copy.id] = copy;
    saveSettings();
    emitCharactersChanged();
    log(`Duplicated character ${source.name || '(unnamed)'}.`);
    return copy;
}

export function renameCharacter(id, name) {
    const record = getCharacterById(id);
    if (!record) return null;
    record.name = String(name ?? '').trim();
    saveSettings();
    emitCharactersChanged();
    return record;
}

export function deleteCharacter(id) {
    const settings = getSettings();
    if (!settings.characters?.[id]) return false;
    delete settings.characters[id];
    if (settings.activeCharacterId === id) {
        const next = Object.values(settings.characters)[0];
        settings.activeCharacterId = next?.id ?? null;
    }
    saveSettings();
    emitCharactersChanged();
    log('Deleted character.');
    return true;
}

export function linkPersona(id, personaKey) {
    const record = getCharacterById(id);
    if (!record) return null;
    record.personaKey = personaKey ?? null;
    saveSettings();
    emitCharactersChanged();
    return record;
}

export async function setActiveCharacter(id) {
    const settings = getSettings();
    if (!settings.characters?.[id]) return null;
    settings.activeCharacterId = id;
    saveSettings();
    emitCharactersChanged();
    return settings.characters[id];
}

export async function syncPersonaForCharacter(character) {
    if (!character?.personaKey) return false;
    const context = getContext();
    const personas = getPersonasMap();
    if (!personas[character.personaKey]) return false;
    try {
        suppressPersonaSync = true;
        if (typeof context.setUserAvatar === 'function') {
            await context.setUserAvatar(character.personaKey);
        } else {
            globalThis.user_avatar = character.personaKey;
            context.eventSource?.emit?.(context.eventTypes?.PERSONA_CHANGED);
        }
    } catch (error) {
        log('Failed to sync persona.', 'warn', error?.message ?? String(error));
        return false;
    } finally {
        suppressPersonaSync = false;
    }
    return true;
}

export function findCharacterForPersona(personaKey) {
    if (!personaKey) return null;
    return listCharacters().find((c) => c.personaKey === personaKey) ?? null;
}

export async function handleExternalPersonaChange(personaKey) {
    const match = findCharacterForPersona(personaKey);
    if (!match) return;
    const settings = getSettings();
    if (settings.activeCharacterId === match.id) return;
    settings.activeCharacterId = match.id;
    saveSettings();
    emitCharactersChanged();
    log(`Switched active character to ${match.name || '(unnamed)'} (persona link).`);
}

export function isPersonaSyncSuppressed() {
    return suppressPersonaSync;
}
