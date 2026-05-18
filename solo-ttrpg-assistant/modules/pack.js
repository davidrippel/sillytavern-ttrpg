// pack.js — v2 (story-mode) pack loader.
//
// The extension reads only a small subset of a pack's files at runtime:
// pack metadata, the character template (to seed new sheets), and the
// advantages/disadvantages reference (for character-sheet autocomplete).
//
// The runtime-injected text content (overlay, complications, reference)
// reaches the GM through the campaign lorebook, not through this
// module. See lorebook_v2.js.

import { parseYaml } from '../lib/yaml.js';
import { PACK_LOREBOOK_ENTRIES, PACK_REQUIRED_FILES } from './constants.js';
import { log } from './logger.js';
import {
    deepClone,
    escapeHtml,
    getContext,
    getSettings,
    isExtensionEnabled,
    saveSettings,
} from './util.js';

const SUPPORTED_PACK_SCHEMA = 2;

const LEGACY_FILES = new Set([
    'attributes.yaml',
    'resources.yaml',
    'abilities.yaml',
    'failure_moves.md',
]);

const LEGACY_TEMPLATE_KEYS = new Set(['attributes', 'abilities', 'equipment', 'state']);

const packSubscribers = new Set();

function emitPackChanged() {
    for (const listener of packSubscribers) listener();
}

export function subscribePack(listener) {
    packSubscribers.add(listener);
    return () => packSubscribers.delete(listener);
}

export function getActivePack() {
    const settings = getSettings();
    if (!settings.activePack && settings.activePackName && settings.packs[settings.activePackName]) {
        settings.activePack = settings.packs[settings.activePackName];
    }
    return settings.activePack ?? null;
}

export function getLoadedPacks() {
    return getSettings().packs ?? {};
}

export function hasActivePack() {
    return Boolean(getActivePack());
}

function validatePackMetadata(metadata) {
    if (!metadata || typeof metadata !== 'object') {
        throw new Error('pack.yaml must parse to an object.');
    }
    for (const field of ['schema_version', 'pack_name', 'display_name', 'version', 'description']) {
        if (metadata[field] === undefined || metadata[field] === null || metadata[field] === '') {
            throw new Error(`pack.yaml is missing required field "${field}".`);
        }
    }
    if (Number(metadata.schema_version) !== SUPPORTED_PACK_SCHEMA) {
        throw new Error(
            `Unsupported pack schema_version "${metadata.schema_version}". `
            + 'This build only loads v2 (story-mode) packs.',
        );
    }
    if (!/^[a-z0-9_]+$/.test(String(metadata.pack_name))) {
        throw new Error('pack.yaml pack_name must be snake_case.');
    }
}

function validateCharacterTemplate(template) {
    if (!template || typeof template !== 'object' || Array.isArray(template)) {
        throw new Error('character_template.json must be an object.');
    }
    const legacyKeysPresent = Object.keys(template).filter((k) => LEGACY_TEMPLATE_KEYS.has(k));
    if (legacyKeysPresent.length > 0) {
        throw new Error(
            `character_template.json contains retired v1 keys (${legacyKeysPresent.join(', ')}). `
            + 'v2 templates use name/concept/advantages/disadvantages/belongings/relationships/notes.',
        );
    }
}

function normalizePack(parsed) {
    const meta = parsed.pack;
    return {
        name: String(meta.pack_name),
        version: String(meta.version),
        displayName: String(meta.display_name),
        description: String(meta.description),
        schemaVersion: Number(meta.schema_version),
        metadata: meta,
        characterTemplate: parsed.characterTemplate,
        advantagesDisadvantagesText: parsed.advantagesDisadvantages ?? '',
        complicationsText: parsed.complications ?? '',
        gmOverlayText: parsed.gmOverlay ?? '',
        toneText: parsed.tone ?? '',
        exampleHooksText: parsed.exampleHooks ?? '',
        generatorSeedDefaults: parsed.generatorSeed ?? {},
        loadedAt: new Date().toISOString(),
    };
}

export async function parsePackFromFiles(fileList) {
    const byName = new Map();
    for (const file of fileList) byName.set(file.name, file);

    // Reject v1 leftovers up front with a clear message.
    const legacyHits = [...byName.keys()].filter((n) => LEGACY_FILES.has(n));
    if (legacyHits.length > 0) {
        throw new Error(
            `This pack contains retired v1 files (${legacyHits.join(', ')}). `
            + 'Migrate the pack to v2 per Docs/02_GENRE_PACK_SPEC.md or regenerate it '
            + 'with the v2 pack generator.',
        );
    }

    for (const filename of PACK_REQUIRED_FILES) {
        if (!byName.has(filename)) {
            throw new Error(`Missing required pack file: ${filename}`);
        }
    }

    const readText = async (name) => {
        try {
            return await byName.get(name).text();
        } catch (error) {
            throw new Error(`Failed to read ${name}: ${error.message}`);
        }
    };

    const [
        packText,
        templateText,
        overlayText,
        toneText,
        complicationsText,
        advantagesText,
        hooksText,
        seedText,
    ] = await Promise.all([
        readText('pack.yaml'),
        readText('character_template.json'),
        readText('gm_prompt_overlay.md'),
        readText('tone.md'),
        readText('complications.md'),
        readText('advantages_disadvantages.md'),
        readText('example_hooks.md'),
        readText('generator_seed.yaml'),
    ]);

    let parsed;
    try {
        parsed = {
            pack: parseYaml(packText),
            characterTemplate: JSON.parse(templateText),
            gmOverlay: overlayText,
            tone: toneText,
            complications: complicationsText,
            advantagesDisadvantages: advantagesText,
            exampleHooks: hooksText,
            generatorSeed: parseYaml(seedText) ?? {},
        };
    } catch (error) {
        throw new Error(error.message);
    }

    validatePackMetadata(parsed.pack);
    validateCharacterTemplate(parsed.characterTemplate);

    return normalizePack(parsed);
}

export function initializeCharacterForPack(pack = getActivePack()) {
    const template = pack?.characterTemplate ?? {
        name: '',
        concept: '',
        advantages: [],
        disadvantages: [],
        belongings: [],
        relationships: [],
        notes: '',
    };
    return deepClone(template);
}

function getActiveCharacterRecord(settings) {
    const id = settings.activeCharacterId;
    return id ? settings.characters?.[id] ?? null : null;
}

export async function setActivePack(packName) {
    const settings = getSettings();
    const pack = settings.packs[packName];
    if (!pack) throw new Error(`Unknown pack "${packName}".`);

    settings.activePackName = packName;
    settings.activePack = pack;
    saveSettings();
    emitPackChanged();
    log(`Activated pack ${pack.displayName} (${pack.version}).`);
    return pack;
}

export async function storeLoadedPack(pack) {
    const settings = getSettings();
    settings.packs[pack.name] = pack;
    settings.activePackName = pack.name;
    settings.activePack = pack;

    const active = getActiveCharacterRecord(settings);
    if (active && !active.packName) {
        active.packName = pack.name;
    }

    saveSettings();
    emitPackChanged();
    log(`Loaded pack ${pack.displayName} (${pack.version}).`);
}

// ---- Lorebook helpers (used by pack-mismatch warnings only) -----------

export function getCurrentChatLorebookName() {
    const context = getContext();
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

function getCharacterLorebookName(context) {
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

export async function loadCurrentLorebook() {
    const context = getContext();
    const chatName = getCurrentChatLorebookName();
    if (chatName) {
        try {
            const book = await context.loadWorldInfo(chatName);
            if (book) return book;
        } catch (error) {
            log(`Failed to load chat lorebook "${chatName}".`, 'warn', error.message);
        }
    }
    const characterName = getCharacterLorebookName(context);
    if (characterName) {
        try {
            const book = await context.loadWorldInfo(characterName);
            if (book) return book;
        } catch (error) {
            log(`Failed to load character lorebook "${characterName}".`, 'warn', error.message);
        }
    }
    return null;
}

function getLorebookEntries(lorebook) {
    if (!lorebook) return [];
    if (Array.isArray(lorebook.entries)) return lorebook.entries;
    if (lorebook.entries && typeof lorebook.entries === 'object') return Object.values(lorebook.entries);
    return [];
}

async function getPackReferenceFromLorebook() {
    const lorebook = await loadCurrentLorebook();
    const entry = getLorebookEntries(lorebook).find(
        (item) => item?.comment === PACK_LOREBOOK_ENTRIES.reference,
    );
    if (!entry?.content) return null;
    // The reference is a markdown document; we only need its associated
    // pack_name/version, which the campaign generator stores in a small
    // JSON header at the top (or as separate keys in the entry's
    // metadata). For now, try parsing as JSON; on failure, return null —
    // mismatch detection becomes best-effort.
    try {
        return JSON.parse(entry.content);
    } catch {
        return null;
    }
}

export async function runCompatibilityCheck({ interactive = false } = {}) {
    if (!isExtensionEnabled()) return null;

    const reference = await getPackReferenceFromLorebook();
    const pack = getActivePack();
    if (!reference || !pack) return null;

    const context = getContext();
    const expectedName = reference.pack_name;
    const expectedVersion = reference.pack_version;

    if (expectedName && expectedName !== pack.name) {
        const message = `This campaign was built for ${escapeHtml(expectedName)}, but the active pack is ${escapeHtml(pack.name)}.`;
        toastr.warning(message);
        if (interactive) await context.Popup.show.text('Pack Mismatch', message);
        log(`Pack mismatch detected: campaign expects ${expectedName}, active pack is ${pack.name}.`, 'warn');
        return { severity: 'warn', message };
    }
    if (expectedVersion && expectedVersion !== pack.version) {
        const message = `This campaign was built for ${escapeHtml(expectedName)}@${escapeHtml(expectedVersion)}, but ${escapeHtml(pack.version)} is loaded.`;
        toastr.info(message);
        log(`Pack version mismatch detected for ${expectedName}: ${expectedVersion} vs ${pack.version}.`, 'info');
        return { severity: 'info', message };
    }

    return { severity: 'ok', message: 'Pack matches campaign.' };
}

export async function saveLorebook(lorebook) {
    const context = getContext();
    const lorebookName = getCurrentChatLorebookName() ?? getCharacterLorebookName(context);
    if (!lorebookName) {
        throw new Error('No active lorebook is bound to the current chat or character.');
    }
    await context.saveWorldInfo(lorebookName, lorebook);
}
