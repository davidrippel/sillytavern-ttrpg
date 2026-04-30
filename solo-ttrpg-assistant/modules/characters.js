import { getActivePack, initializeCharacterForPack, setActivePack } from './pack.js';
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
    for (const listener of characterSubscribers) {
        listener();
    }
}

export function subscribeCharacters(listener) {
    characterSubscribers.add(listener);
    return () => characterSubscribers.delete(listener);
}

export function emitCharacterMetaChanged() {
    for (const listener of characterMetaSubscribers) {
        listener();
    }
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

    // If we have characters but no active one, adopt the first.
    const first = Object.values(settings.characters ?? {})[0];
    if (first) {
        settings.activeCharacterId = first.id;
        return first;
    }

    return null;
}

export function ensureActiveCharacter() {
    const settings = getSettings();
    const existing = getActiveCharacter();
    if (existing) {
        return existing;
    }

    const created = createCharacter({ name: '', packName: settings.activePackName ?? null });
    return created;
}

function buildCharacterRecord({ name = '', packName = null, personaKey = null } = {}) {
    const pack = getSettings().packs?.[packName] ?? null;
    const base = initializeCharacterForPack(pack ?? getActivePack());
    return {
        ...base,
        id: newCharacterId(),
        mode: 'pack',
        name: name || base.name || '',
        packName: packName ?? getSettings().activePackName ?? null,
        personaKey: personaKey ?? null,
    };
}

function buildStoryCharacterRecord({
    name = '',
    description = '',
    strengths = [],
    weakness = '',
    notes = '',
    personaKey = null,
} = {}) {
    return {
        id: newCharacterId(),
        mode: 'story',
        name: name || '',
        packName: null,
        personaKey: personaKey ?? null,
        description: String(description ?? ''),
        strengths: Array.isArray(strengths) ? strengths.slice(0, 2).map((value) => String(value)) : [],
        weakness: String(weakness ?? ''),
        notes: String(notes ?? ''),
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

export function createStoryCharacter(options = {}) {
    const settings = getSettings();
    const record = buildStoryCharacterRecord(options);
    settings.characters[record.id] = record;
    settings.activeCharacterId = record.id;
    saveSettings();
    log(`Created story character ${record.name || '(unnamed)'}.`);
    emitCharactersChanged();
    return record;
}

export function duplicateCharacter(id) {
    const source = getCharacterById(id);
    if (!source) {
        return null;
    }

    const settings = getSettings();
    const copy = structuredClone(source);
    copy.id = newCharacterId();
    copy.name = `${source.name || 'Character'} (copy)`;
    settings.characters[copy.id] = copy;
    settings.activeCharacterId = copy.id;
    saveSettings();
    log(`Duplicated character ${source.name || '(unnamed)'}.`);
    emitCharactersChanged();
    return copy;
}

export function renameCharacter(id, name) {
    const record = getCharacterById(id);
    if (!record) {
        return null;
    }
    record.name = String(name ?? '');
    saveSettings();
    emitCharactersChanged();
    return record;
}

export function deleteCharacter(id) {
    const settings = getSettings();
    if (!settings.characters?.[id]) {
        return false;
    }

    const remaining = Object.keys(settings.characters).filter((key) => key !== id);
    if (remaining.length === 0) {
        throw new Error('Cannot delete the last character.');
    }

    const wasActive = settings.activeCharacterId === id;
    delete settings.characters[id];
    if (wasActive) {
        settings.activeCharacterId = remaining[0];
    }
    saveSettings();
    log('Deleted character.');
    emitCharactersChanged();

    if (wasActive) {
        void setActiveCharacter(settings.activeCharacterId);
    }
    return true;
}

export function linkPersona(id, personaKey) {
    const record = getCharacterById(id);
    if (!record) {
        return null;
    }
    record.personaKey = personaKey ?? null;
    saveSettings();
    emitCharactersChanged();
    return record;
}

export async function setActiveCharacter(id) {
    const settings = getSettings();
    const target = settings.characters?.[id];
    if (!target) {
        throw new Error(`Unknown character "${id}".`);
    }

    settings.activeCharacterId = id;
    saveSettings();

    // Pack sync
    if (target.packName && target.packName !== settings.activePackName && settings.packs?.[target.packName]) {
        try {
            await setActivePack(target.packName);
        } catch (error) {
            log(`Failed to switch pack for character: ${error.message}`, 'warn');
        }
    }

    // Persona sync
    if (target.personaKey && !suppressPersonaSync) {
        await syncPersonaForCharacter(target);
    }

    emitCharactersChanged();
    return target;
}

export async function syncPersonaForCharacter(character) {
    if (!character?.personaKey) {
        return;
    }

    const personas = getPersonasMap();
    const displayName = personas[character.personaKey];
    if (!displayName) {
        return;
    }

    const currentKey = await getCurrentPersonaKey();
    if (currentKey === character.personaKey) {
        return;
    }

    const context = getContext();
    try {
        suppressPersonaSync = true;
        if (typeof context.executeSlashCommandsWithOptions === 'function') {
            await context.executeSlashCommandsWithOptions(`/persona ${escapeForSlash(displayName)}`);
        }
    } catch (error) {
        log(`Failed to switch persona: ${error.message}`, 'warn');
    } finally {
        suppressPersonaSync = false;
    }
}

function escapeForSlash(value) {
    const text = String(value ?? '');
    if (/\s|"/.test(text)) {
        return `"${text.replaceAll('"', '\\"')}"`;
    }
    return text;
}

export function findCharacterForPersona(personaKey) {
    if (!personaKey) {
        return null;
    }
    return listCharacters().find((character) => character.personaKey === personaKey) ?? null;
}

export async function handleExternalPersonaChange(personaKey) {
    if (suppressPersonaSync || !personaKey) {
        return null;
    }

    const match = findCharacterForPersona(personaKey);
    if (!match) {
        return null;
    }

    const settings = getSettings();
    if (settings.activeCharacterId === match.id) {
        return match;
    }

    try {
        suppressPersonaSync = true;
        settings.activeCharacterId = match.id;
        saveSettings();

        if (match.packName && match.packName !== settings.activePackName && settings.packs?.[match.packName]) {
            try {
                await setActivePack(match.packName);
            } catch (error) {
                log(`Failed to switch pack for character: ${error.message}`, 'warn');
            }
        }

        emitCharactersChanged();
        return match;
    } finally {
        suppressPersonaSync = false;
    }
}

export function isPersonaSyncSuppressed() {
    return suppressPersonaSync;
}
