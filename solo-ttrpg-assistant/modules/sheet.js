import { findAbilityDefinition, getActivePack, hasActivePack, initializeCharacterForPack, subscribePack } from './pack.js';
import { log } from './logger.js';
import {
    escapeHtml,
    formatSignedNumber,
    getContext,
    getSettings,
    normalizeName,
    saveSettings,
} from './util.js';

const sheetSubscribers = new Set();
let rootElement = null;
let modeElement = null;

function setModeLabel(text) {
    if (!modeElement) {
        return;
    }

    modeElement.textContent = text;
}

function emitSheetChanged() {
    for (const listener of sheetSubscribers) {
        listener();
    }
}

export function subscribeSheet(listener) {
    sheetSubscribers.add(listener);
    return () => sheetSubscribers.delete(listener);
}

export function getCharacter() {
    const settings = getSettings();
    if (!settings.character) {
        settings.character = initializeCharacterForPack();
    }
    return settings.character;
}

export function saveCharacter() {
    saveSettings();
    emitSheetChanged();
}

export function ensureCharacter() {
    const settings = getSettings();
    if (!settings.character) {
        settings.character = initializeCharacterForPack();
    }
    return settings.character;
}

export function resetCharacterForActivePack() {
    getSettings().character = initializeCharacterForPack();
    saveCharacter();
    log('Character sheet reset from pack template.');
}

function getAbilityLabel(ability) {
    if (typeof ability === 'string') {
        return ability;
    }

    if (!ability || typeof ability !== 'object') {
        return '';
    }

    const level = ability.level ? ` (${ability.level})` : '';
    return `${ability.name ?? ''}${level}`;
}

function getResourceDisplay(character, resource) {
    const value = character.state?.[resource.key];

    if (resource.kind === 'pool' || resource.kind === 'pool_with_threshold') {
        const maxKey = resource.max_value_field;
        const maxValue = maxKey ? character.state?.[maxKey] : resource.threshold_field ? character.state?.[resource.threshold_field] : null;
        return `${value ?? 0}/${maxValue ?? '?'}`;
    }

    if (resource.kind === 'toggle') {
        return value ? 'On' : 'Off';
    }

    if (resource.kind === 'track' && Array.isArray(value)) {
        return value.join(', ');
    }

    return String(value ?? '');
}

export function formatCharacterSheetForPrompt() {
    const character = getCharacter();
    const pack = getActivePack();

    if (!pack) {
        const lines = [
            '=== CHARACTER SHEET ===',
            `Name: ${character.name || 'Unknown'}`,
            `Concept: ${character.concept || 'Unknown'}`,
            `Attributes: ${Object.entries(character.attributes ?? {}).map(([key, value]) => `${key} ${formatSignedNumber(value)}`).join(' | ') || 'none'}`,
            `State: ${Object.entries(character.state ?? {}).map(([key, value]) => `${key} ${Array.isArray(value) ? value.join(', ') : value}`).join(' | ') || 'none'}`,
        ];
        if (character.notes) {
            lines.push(`Notes: ${character.notes}`);
        }
        return lines.join('\n');
    }

    const lines = [
        '=== CHARACTER SHEET ===',
        `Name: ${character.name || 'Unknown'}`,
        `Concept: ${character.concept || 'Unknown'}`,
        `Attributes: ${pack.attributes.map((attribute) => `${attribute.display} ${formatSignedNumber(character.attributes?.[attribute.key] ?? 0)}`).join(' | ')}`,
    ];

    const abilities = (character.abilities ?? []).map(getAbilityLabel).filter(Boolean);
    if (abilities.length > 0) {
        lines.push(`Abilities: ${abilities.join(', ')}`);
    }

    const stateParts = pack.resources
        .filter((resource) => resource.kind !== 'static_value')
        .map((resource) => `${resource.display} ${getResourceDisplay(character, resource)}`);
    if (stateParts.length > 0) {
        lines.push(`State: ${stateParts.join(' | ')}`);
    }

    if (Array.isArray(character.state?.conditions) && character.state.conditions.length > 0) {
        lines.push(`Conditions: ${character.state.conditions.join(', ')}`);
    }

    if ((character.equipment ?? []).length > 0) {
        lines.push(`Equipment: ${character.equipment.join(', ')}`);
    }

    if (character.notes) {
        lines.push(`Notes: ${character.notes}`);
    }

    return lines.join('\n');
}

function createListEditor(title, items, onAdd, onRemove) {
    const $section = $('<section class="solo-section solo-stack"></section>');
    $section.append(`<div class="solo-row spread"><h5>${escapeHtml(title)}</h5></div>`);

    const $list = $('<div class="solo-pill-list"></div>');
    for (const [index, item] of items.entries()) {
        const label = getAbilityLabel(item) || String(item);
        const $pill = $(`<span class="solo-pill"><span>${escapeHtml(label)}</span></span>`);
        const $remove = $('<button class="menu_button menu_button_icon" title="Remove"><i class="fa-solid fa-xmark"></i></button>');
        $remove.on('click', () => onRemove(index));
        $pill.append($remove);
        $list.append($pill);
    }
    $section.append($list);

    const $row = $('<div class="solo-row"></div>');
    const $input = $('<input type="text" />');
    const $button = $('<button class="menu_button">Add</button>');
    $button.on('click', () => {
        const value = $input.val().trim();
        if (!value) {
            return;
        }
        onAdd(value);
        $input.val('');
    });
    $row.append($input, $button);
    $section.append($row);

    return $section;
}

function renderDegradedSheet($root) {
    const character = ensureCharacter();
    setModeLabel('Unknown pack mode');

    const $base = $('<section class="solo-section solo-stack"></section>');
    $base.append('<div class="solo-row spread"><h5>Core</h5></div>');
    const $name = $(`<label class="solo-stack"><span>Name</span><input type="text" value="${escapeHtml(character.name ?? '')}" /></label>`);
    const $concept = $(`<label class="solo-stack"><span>Concept</span><input type="text" value="${escapeHtml(character.concept ?? '')}" /></label>`);
    $name.find('input').on('input', (event) => {
        character.name = event.target.value;
        saveCharacter();
    });
    $concept.find('input').on('input', (event) => {
        character.concept = event.target.value;
        saveCharacter();
    });
    $base.append($name, $concept);

    const attributesValue = JSON.stringify(character.attributes ?? {}, null, 2);
    const stateValue = JSON.stringify(character.state ?? {}, null, 2);
    const $attributes = $(`<label class="solo-stack"><span>Attributes JSON</span><textarea class="solo-code">${escapeHtml(attributesValue)}</textarea></label>`);
    const $state = $(`<label class="solo-stack"><span>State JSON</span><textarea class="solo-code">${escapeHtml(stateValue)}</textarea></label>`);
    const $notes = $(`<label class="solo-stack"><span>Notes</span><textarea>${escapeHtml(character.notes ?? '')}</textarea></label>`);

    $attributes.find('textarea').on('change', (event) => {
        try {
            character.attributes = JSON.parse(event.target.value || '{}');
            saveCharacter();
        } catch {
            toastr.error('Invalid JSON in attributes.');
        }
    });
    $state.find('textarea').on('change', (event) => {
        try {
            character.state = JSON.parse(event.target.value || '{}');
            saveCharacter();
        } catch {
            toastr.error('Invalid JSON in state.');
        }
    });
    $notes.find('textarea').on('input', (event) => {
        character.notes = event.target.value;
        saveCharacter();
    });

    $root.append($base, $attributes, $state, $notes);
}

function renderPackSheet($root) {
    const pack = getActivePack();
    const character = ensureCharacter();
    setModeLabel(pack.displayName);

    const $base = $('<section class="solo-section solo-stack"></section>');
    $base.append('<div class="solo-row spread"><h5>Core</h5></div>');
    const $name = $(`<label class="solo-stack"><span>Name</span><input type="text" value="${escapeHtml(character.name ?? '')}" /></label>`);
    const $concept = $(`<label class="solo-stack"><span>Concept</span><input type="text" value="${escapeHtml(character.concept ?? '')}" /></label>`);
    $name.find('input').on('input', (event) => {
        character.name = event.target.value;
        saveCharacter();
    });
    $concept.find('input').on('input', (event) => {
        character.concept = event.target.value;
        saveCharacter();
    });
    $base.append($name, $concept);
    $root.append($base);

    const $attributes = $('<section class="solo-section solo-stack"></section>');
    $attributes.append('<div class="solo-row spread"><h5>Attributes</h5></div>');
    const $attrGrid = $('<div class="solo-kv compact"></div>');
    for (const attribute of pack.attributes) {
        const currentValue = Number(character.attributes?.[attribute.key] ?? 0);
        $attrGrid.append(`<span title="${escapeHtml(attribute.description ?? '')}">${escapeHtml(attribute.display)}</span>`);
        const $input = $(`<input type="number" value="${currentValue}" step="1" />`);
        $input.on('input', (event) => {
            character.attributes[attribute.key] = Number(event.target.value || 0);
            saveCharacter();
        });
        $attrGrid.append($input);
    }
    $attributes.append($attrGrid);
    $root.append($attributes);

    const $state = $('<section class="solo-section solo-stack"></section>');
    $state.append('<div class="solo-row spread"><h5>State</h5></div>');
    for (const resource of pack.resources) {
        const currentValue = character.state?.[resource.key] ?? resource.starting_value ?? 0;
        const $row = $('<div class="solo-resource solo-stack"></div>');
        $row.append(`<div class="solo-row spread"><strong>${escapeHtml(resource.display)}</strong><span>${escapeHtml(getResourceDisplay(character, resource))}</span></div>`);

        if (resource.kind === 'pool' || resource.kind === 'pool_with_threshold' || resource.kind === 'counter' || resource.kind === 'static_value') {
            const $input = $(`<input type="number" value="${Number(currentValue) || 0}" step="1" />`);
            $input.on('input', (event) => {
                character.state[resource.key] = Number(event.target.value || 0);
                saveCharacter();
            });
            $row.append($input);
        } else if (resource.kind === 'toggle') {
            const checked = Boolean(currentValue);
            const $input = $(`<label class="solo-row"><input type="checkbox" ${checked ? 'checked' : ''} /><span>Enabled</span></label>`);
            $input.find('input').on('input', (event) => {
                character.state[resource.key] = Boolean(event.target.checked);
                saveCharacter();
            });
            $row.append($input);
        }

        if (resource.kind === 'pool' || resource.kind === 'pool_with_threshold') {
            const maxKey = resource.max_value_field ?? resource.threshold_field;
            const maxValue = Number(character.state?.[maxKey] ?? 0) || 0;
            const value = Number(currentValue) || 0;
            const ratio = maxValue > 0 ? Math.min(100, Math.max(0, (value / maxValue) * 100)) : 0;
            $row.append(`<div class="solo-progress"><span style="width:${ratio}%"></span></div>`);
        }

        $state.append($row);
    }
    $root.append($state);

    const abilities = character.abilities ?? (character.abilities = []);
    const $abilities = createListEditor(
        'Abilities',
        abilities,
        (name) => {
            const definition = findAbilityDefinition(name, pack);
            abilities.push(definition ? {
                name: definition.name,
                category: definition.category,
                level: pack.abilityCategoryMap[definition.category]?.has_levels ? pack.abilityCategoryMap[definition.category]?.level_names?.[0] ?? '' : '',
            } : { name });
            saveCharacter();
        },
        (index) => {
            abilities.splice(index, 1);
            saveCharacter();
        },
    );
    const $catalogButton = $('<button class="menu_button">Add From Catalog</button>');
    $catalogButton.on('click', async () => {
        const context = getContext();
        const options = pack.abilityCatalog.map((ability) => `<option value="${escapeHtml(ability.name)}">${escapeHtml(ability.name)} (${escapeHtml(pack.abilityCategoryMap[ability.category]?.display ?? ability.category)})</option>`).join('');
        const html = `<label class="solo-stack"><span>Ability</span><select id="solo-catalog-select">${options}</select></label>`;
        const popup = new context.Popup(html, context.POPUP_TYPE.TEXT, 'Add Ability', { okButton: 'Add' });
        const result = await popup.show();
        if (result === context.POPUP_RESULT.AFFIRMATIVE) {
            const selected = popup.dom?.querySelector?.('#solo-catalog-select')?.value;
            if (selected) {
                const definition = findAbilityDefinition(selected, pack);
                abilities.push(definition ? {
                    name: definition.name,
                    category: definition.category,
                    level: pack.abilityCategoryMap[definition.category]?.has_levels ? pack.abilityCategoryMap[definition.category]?.level_names?.[0] ?? '' : '',
                } : { name: selected });
                saveCharacter();
            }
        }
    });
    $abilities.append($catalogButton);
    $root.append($abilities);

    const equipment = character.equipment ?? (character.equipment = []);
    $root.append(createListEditor('Equipment', equipment, (item) => {
        equipment.push(item);
        saveCharacter();
    }, (index) => {
        equipment.splice(index, 1);
        saveCharacter();
    }));

    if (!Array.isArray(character.state.conditions)) {
        character.state.conditions = [];
    }
    $root.append(createListEditor('Conditions', character.state.conditions, (item) => {
        character.state.conditions.push(item);
        saveCharacter();
    }, (index) => {
        character.state.conditions.splice(index, 1);
        saveCharacter();
    }));

    const $notes = $(`<section class="solo-section solo-stack"><div class="solo-row spread"><h5>Notes</h5></div><textarea>${escapeHtml(character.notes ?? '')}</textarea></section>`);
    $notes.find('textarea').on('input', (event) => {
        character.notes = event.target.value;
        saveCharacter();
    });
    $root.append($notes);

    const $summary = $('<section class="solo-section solo-stack"></section>');
    $summary.append('<div class="solo-row spread"><h5>Prompt Preview</h5></div>');
    $summary.append(`<div class="solo-code">${escapeHtml(formatCharacterSheetForPrompt())}</div>`);
    $root.append($summary);
}

export function renderSheet() {
    if (!rootElement) {
        return;
    }

    const $root = $(rootElement);
    $root.empty();

    if (!hasActivePack()) {
        renderDegradedSheet($root);
        return;
    }

    renderPackSheet($root);
}

export function mountSheet(root, modeLabel) {
    rootElement = root;
    modeElement = modeLabel;

    subscribePack(() => {
        const settings = getSettings();
        if (!settings.character) {
            settings.character = initializeCharacterForPack();
        }
        renderSheet();
    });

    subscribeSheet(() => renderSheet());
    renderSheet();
}

export function findAbilityOnSheet(name) {
    const character = getCharacter();
    return (character.abilities ?? []).find((ability) => normalizeName(typeof ability === 'string' ? ability : ability?.name) === normalizeName(name)) ?? null;
}

export function buildRecentChatExcerpt(limit = 8) {
    const context = getContext();
    return (context.chat ?? [])
        .slice(-limit)
        .map((message) => `${message.is_user ? 'Player' : (message.name || 'GM')}: ${message.mes || ''}`)
        .join('\n\n');
}
