import { parseYaml } from '../lib/yaml.js';
import { PACK_REQUIRED_FILES } from './constants.js';
import { log } from './logger.js';
import {
    deepClone,
    escapeHtml,
    getContext,
    getSettings,
    normalizeName,
    saveSettings,
} from './util.js';

const packSubscribers = new Set();

function emitPackChanged() {
    for (const listener of packSubscribers) {
        listener();
    }
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
        if (!metadata[field]) {
            throw new Error(`pack.yaml is missing required field "${field}".`);
        }
    }

    if (metadata.schema_version !== 1) {
        throw new Error(`Unsupported pack schema_version "${metadata.schema_version}".`);
    }

    if (!/^[a-z0-9_]+$/.test(metadata.pack_name)) {
        throw new Error('pack.yaml pack_name must be snake_case.');
    }
}

function validateAttributes(attributesDoc) {
    const attributes = attributesDoc?.attributes;
    if (!Array.isArray(attributes) || attributes.length !== 6) {
        throw new Error('attributes.yaml must define exactly 6 attributes.');
    }

    const keys = new Set();
    for (const attribute of attributes) {
        if (!attribute?.key || !attribute?.display) {
            throw new Error('Each attribute must include key and display.');
        }
        if (keys.has(attribute.key)) {
            throw new Error(`Duplicate attribute key "${attribute.key}".`);
        }
        keys.add(attribute.key);
    }
}

function validateResources(resourcesDoc) {
    const resources = resourcesDoc?.resources;
    if (!Array.isArray(resources) || resources.length === 0) {
        throw new Error('resources.yaml must define at least one resource.');
    }

    const keys = new Set(resources.map((resource) => resource?.key));
    if (!keys.has('hp_current') || !keys.has('hp_max')) {
        throw new Error('resources.yaml must include hp_current and hp_max.');
    }
}

function validateAbilities(abilitiesDoc) {
    if (!Array.isArray(abilitiesDoc?.categories)) {
        throw new Error('abilities.yaml must define categories.');
    }

    if (!Array.isArray(abilitiesDoc?.catalog)) {
        throw new Error('abilities.yaml must define catalog.');
    }
}

function validateCharacterTemplate(template) {
    if (!template || typeof template !== 'object' || Array.isArray(template)) {
        throw new Error('character_template.json must be an object.');
    }
}

function normalizePack(parsed) {
    const attributeMap = Object.fromEntries(parsed.attributes.attributes.map((attribute) => [attribute.key, attribute]));
    const resourceMap = Object.fromEntries(parsed.resources.resources.map((resource) => [resource.key, resource]));
    const abilityCategoryMap = Object.fromEntries(parsed.abilities.categories.map((category) => [category.key, category]));

    return {
        name: parsed.pack.pack_name,
        version: String(parsed.pack.version),
        displayName: String(parsed.pack.display_name),
        description: String(parsed.pack.description),
        metadata: parsed.pack,
        attributes: parsed.attributes.attributes,
        attributeMap,
        resources: parsed.resources.resources,
        resourceMap,
        abilities: parsed.abilities.catalog,
        abilityCatalog: parsed.abilities.catalog,
        abilityCategories: parsed.abilities.categories,
        abilityCategoryMap,
        characterTemplate: parsed.characterTemplate,
        loadedAt: new Date().toISOString(),
    };
}

export async function parsePackFromFiles(fileList) {
    const byName = new Map();
    for (const file of fileList) {
        byName.set(file.name, file);
    }

    for (const filename of PACK_REQUIRED_FILES) {
        if (!byName.has(filename)) {
            throw new Error(`Missing required pack file: ${filename}`);
        }
    }

    const [packText, attributesText, resourcesText, abilitiesText, characterTemplateText] = await Promise.all(
        PACK_REQUIRED_FILES.map(async (filename) => {
            try {
                return await byName.get(filename).text();
            } catch (error) {
                throw new Error(`Failed to read ${filename}: ${error.message}`);
            }
        }),
    );

    let parsed;
    try {
        parsed = {
            pack: parseYaml(packText),
            attributes: parseYaml(attributesText),
            resources: parseYaml(resourcesText),
            abilities: parseYaml(abilitiesText),
            characterTemplate: JSON.parse(characterTemplateText),
        };
    } catch (error) {
        throw new Error(error.message);
    }

    validatePackMetadata(parsed.pack);
    validateAttributes(parsed.attributes);
    validateResources(parsed.resources);
    validateAbilities(parsed.abilities);
    validateCharacterTemplate(parsed.characterTemplate);

    return normalizePack(parsed);
}

export function isCharacterCompatibleWithPack(character, pack = getActivePack()) {
    if (!character || !pack) {
        return true;
    }

    const template = pack.characterTemplate ?? {};
    const templateAttributes = Object.keys(template.attributes ?? {});
    const currentAttributes = Object.keys(character.attributes ?? {});
    const templateResources = Object.keys(template.state ?? {});
    const currentResources = Object.keys(character.state ?? {});

    return templateAttributes.every((key) => currentAttributes.includes(key))
        && templateResources.every((key) => currentResources.includes(key));
}

export function initializeCharacterForPack(pack = getActivePack()) {
    if (!pack) {
        return {
            name: '',
            concept: '',
            attributes: {},
            abilities: [],
            equipment: [],
            state: {},
            notes: '',
        };
    }

    return deepClone(pack.characterTemplate);
}

function getActiveCharacterRecord(settings) {
    const id = settings.activeCharacterId;
    return id ? settings.characters?.[id] ?? null : null;
}

export async function setActivePack(packName, { preserveCharacter = true } = {}) {
    const settings = getSettings();
    const pack = settings.packs[packName];

    if (!pack) {
        throw new Error(`Unknown pack "${packName}".`);
    }

    const active = getActiveCharacterRecord(settings);
    if (!preserveCharacter && active && !isCharacterCompatibleWithPack(active, pack)) {
        Object.assign(active, initializeCharacterForPack(pack));
        active.packName = packName;
    }

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
    if (active && !isCharacterCompatibleWithPack(active, pack)) {
        Object.assign(active, initializeCharacterForPack(pack));
        active.packName = pack.name;
    } else if (active && !active.packName) {
        active.packName = pack.name;
    }

    saveSettings();
    emitPackChanged();
    log(`Loaded pack ${pack.displayName} (${pack.version}).`);
}

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
        if (typeof candidate === 'string' && candidate.trim()) {
            return candidate;
        }

        if (candidate && typeof candidate === 'object') {
            for (const key of ['name', 'world', 'selected']) {
                if (typeof candidate[key] === 'string' && candidate[key].trim()) {
                    return candidate[key];
                }
            }
        }
    }

    return null;
}

export async function loadCurrentLorebook() {
    const context = getContext();
    const lorebookName = getCurrentChatLorebookName();
    if (!lorebookName) {
        return null;
    }

    try {
        return await context.loadWorldInfo(lorebookName);
    } catch (error) {
        log(`Failed to load lorebook "${lorebookName}".`, 'warn', error.message);
        return null;
    }
}

function getLorebookEntries(lorebook) {
    if (!lorebook) {
        return [];
    }

    if (Array.isArray(lorebook.entries)) {
        return lorebook.entries;
    }

    if (lorebook.entries && typeof lorebook.entries === 'object') {
        return Object.values(lorebook.entries);
    }

    return [];
}

export async function getPackReferenceFromLorebook() {
    const lorebook = await loadCurrentLorebook();
    const entry = getLorebookEntries(lorebook).find((item) => item?.comment === '__pack_reference');

    if (!entry?.content) {
        return null;
    }

    try {
        return JSON.parse(entry.content);
    } catch (error) {
        log('Failed to parse __pack_reference entry.', 'warn', error.message);
        return null;
    }
}

export async function runCompatibilityCheck({ interactive = false } = {}) {
    const reference = await getPackReferenceFromLorebook();
    const pack = getActivePack();

    if (!reference || !pack) {
        return null;
    }

    const context = getContext();
    const expectedName = reference.pack_name;
    const expectedVersion = reference.pack_version;

    if (expectedName !== pack.name) {
        const message = `This campaign was built for ${escapeHtml(expectedName)}, but the active pack is ${escapeHtml(pack.name)}. Dice rolls and the sheet may not line up.`;
        toastr.warning(message);

        if (interactive) {
            await context.Popup.show.text('Pack Mismatch', message);
        }

        log(`Pack mismatch detected: campaign expects ${expectedName}, active pack is ${pack.name}.`, 'warn');
        return { severity: 'warn', message };
    }

    if (expectedVersion !== pack.version) {
        const message = `This campaign was built for ${escapeHtml(expectedName)}@${escapeHtml(expectedVersion)}, but ${escapeHtml(pack.version)} is loaded.`;
        toastr.info(message);
        log(`Pack version mismatch detected for ${expectedName}: ${expectedVersion} vs ${pack.version}.`, 'info');
        return { severity: 'info', message };
    }

    return { severity: 'ok', message: 'Pack matches campaign.' };
}

export function findAbilityDefinition(name, pack = getActivePack()) {
    if (!pack || !name) {
        return null;
    }

    const normalized = normalizeName(name);
    return pack.abilityCatalog.find((ability) => normalizeName(ability.name) === normalized) ?? null;
}

export async function saveLorebook(lorebook) {
    const context = getContext();
    const lorebookName = getCurrentChatLorebookName();
    if (!lorebookName) {
        throw new Error('No active chat lorebook is bound to the current chat.');
    }

    await context.saveWorldInfo(lorebookName, lorebook);
}
