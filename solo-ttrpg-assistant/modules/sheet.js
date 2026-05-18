// sheet.js — character sheet rendering (v3, story-mode).
//
// The sheet works against the v2 character template shape:
//   { name, concept, advantages[], disadvantages[], belongings[],
//     relationships[{ name, tie }], notes }
//
// There are no attribute scores, abilities, equipment lists with
// quantities, hit-point pools, or status fields. Everything is short
// strings the player and the GM can read at a glance.

import { emitCharacterMetaChanged, getActiveCharacter } from './characters.js';
import { getActivePack, initializeCharacterForPack, subscribePack } from './pack.js';
import { getContext, getSettings, saveSettings } from './util.js';
import { parseAdvantagesDisadvantages } from './vocabulary.js';

const sheetSubscribers = new Set();
const sheetStateSubscribers = new Set();
let $sheetRoot = null;

function emitSheetChanged() {
    for (const listener of sheetSubscribers) listener();
}

function emitSheetState() {
    for (const listener of sheetStateSubscribers) listener();
}

export function subscribeSheet(listener) {
    sheetSubscribers.add(listener);
    return () => sheetSubscribers.delete(listener);
}

export function subscribeSheetState(listener) {
    sheetStateSubscribers.add(listener);
    return () => sheetStateSubscribers.delete(listener);
}

export function getCharacter() {
    return getActiveCharacter();
}

export function saveCharacter({ rerender = true } = {}) {
    saveSettings();
    emitSheetChanged();
    emitCharacterMetaChanged();
    if (rerender && $sheetRoot) renderSheet();
}

export function ensureCharacter() {
    const character = getCharacter();
    if (character) return character;
    const pack = getActivePack();
    const settings = getSettings();
    const template = initializeCharacterForPack(pack);
    const id = `char_${Date.now().toString(36)}`;
    const record = { ...template, id, packName: settings.activePackName ?? null, personaKey: null };
    settings.characters[id] = record;
    settings.activeCharacterId = id;
    saveSettings();
    emitSheetChanged();
    return record;
}

export function resetCharacterForActivePack() {
    const character = getCharacter();
    if (!character) return;
    const pack = getActivePack();
    const template = initializeCharacterForPack(pack);
    Object.assign(character, template, {
        id: character.id,
        name: character.name,
        packName: pack?.name ?? character.packName,
        personaKey: character.personaKey,
    });
    saveCharacter();
}

// ---- Prompt-side rendering --------------------------------------------

/**
 * Inline character-sheet block that the generate-interceptor injects
 * into the chat just before the Author's Note. Kept short — the GM
 * only needs the high-signal fields.
 */
export function formatCharacterSheetForPrompt() {
    const character = getCharacter();
    if (!character) return '[No character set.]';

    const lines = ['Character Sheet (story-mode):'];
    if (character.name) lines.push(`Name: ${character.name}`);
    if (character.concept) lines.push(`Concept: ${character.concept}`);

    const advantages = arrayOf(character.advantages);
    if (advantages.length > 0) {
        lines.push('Advantages:');
        for (const item of advantages) lines.push(`  - ${item}`);
    }

    const disadvantages = arrayOf(character.disadvantages);
    if (disadvantages.length > 0) {
        lines.push('Disadvantages:');
        for (const item of disadvantages) lines.push(`  - ${item}`);
    }

    const belongings = arrayOf(character.belongings);
    if (belongings.length > 0) {
        lines.push('Belongings:');
        for (const item of belongings) lines.push(`  - ${item}`);
    }

    const relationships = Array.isArray(character.relationships) ? character.relationships : [];
    if (relationships.length > 0) {
        lines.push('Relationships:');
        for (const rel of relationships) {
            if (!rel) continue;
            const name = String(rel.name ?? '').trim();
            const tie = String(rel.tie ?? '').trim();
            if (!name) continue;
            lines.push(`  - ${name}${tie ? ` — ${tie}` : ''}`);
        }
    }

    return lines.join('\n');
}

function arrayOf(value) {
    if (!Array.isArray(value)) return [];
    return value.map((item) => String(item ?? '').trim()).filter(Boolean);
}

// ---- DOM rendering ----------------------------------------------------

export function mountSheet(root) {
    $sheetRoot = root instanceof globalThis.jQuery ? root : globalThis.$(root);
    renderSheet();
    subscribePack(() => renderSheet());
}

export function renderSheet() {
    if (!$sheetRoot) return;
    const character = getCharacter();
    $sheetRoot.empty();

    if (!character) {
        $sheetRoot.append(
            $('<div></div>')
                .addClass('solo-empty')
                .text('No character yet — create one from the Character panel.'),
        );
        return;
    }

    const pack = getActivePack();
    const vocabulary = parseAdvantagesDisadvantages(pack?.advantagesDisadvantagesText ?? '');

    $sheetRoot.append(renderField('name', 'Name', character.name ?? '', { multiline: false }));
    $sheetRoot.append(renderField('concept', 'Concept', character.concept ?? '', {
        multiline: true,
        placeholder: '1–2 sentences. Who they are, what drew them in, one complication.',
    }));
    $sheetRoot.append(renderListField('advantages', 'Advantages', character.advantages, {
        placeholder: 'e.g. "trained witchsight"',
        vocabularyGroups: vocabulary.advantages,
    }));
    $sheetRoot.append(renderListField('disadvantages', 'Disadvantages', character.disadvantages, {
        placeholder: 'e.g. "known to the inquisition"',
        vocabularyGroups: vocabulary.disadvantages,
    }));
    $sheetRoot.append(renderListField('belongings', 'Belongings', character.belongings, {
        placeholder: 'a notable item',
    }));
    $sheetRoot.append(renderRelationships(character.relationships));
    $sheetRoot.append(renderField('notes', 'Notes', character.notes ?? '', {
        multiline: true,
        placeholder: 'Private notes (not sent to the GM).',
    }));

    emitSheetState();
}

function renderField(key, label, value, { multiline = false, placeholder = '' } = {}) {
    const $wrap = $('<div></div>').addClass('solo-field');
    $wrap.append($('<label></label>').text(label));
    const $input = multiline
        ? $('<textarea rows="3"></textarea>')
        : $('<input type="text" />');
    $input.attr('placeholder', placeholder).val(value);
    $input.on('change blur', () => {
        const character = getCharacter();
        if (!character) return;
        character[key] = String($input.val() ?? '');
        saveCharacter({ rerender: false });
    });
    $wrap.append($input);
    return $wrap;
}

function renderListField(key, label, value, { placeholder = '', vocabularyGroups = null } = {}) {
    const items = Array.isArray(value) ? value : [];
    const $wrap = $('<div></div>').addClass('solo-field solo-field-list');
    $wrap.append($('<label></label>').text(label));

    const $list = $('<ul></ul>').addClass('solo-list');
    items.forEach((item, index) => {
        const $row = $('<li></li>').addClass('solo-list-row');
        const $input = $('<input type="text" />').val(item).attr('placeholder', placeholder);
        $input.on('change blur', () => {
            const character = getCharacter();
            if (!character) return;
            const arr = Array.isArray(character[key]) ? character[key].slice() : [];
            arr[index] = String($input.val() ?? '').trim();
            character[key] = arr.filter(Boolean);
            saveCharacter({ rerender: false });
        });
        const $remove = $('<button type="button" title="Remove"></button>')
            .addClass('solo-list-remove')
            .text('×')
            .on('click', () => {
                const character = getCharacter();
                if (!character) return;
                const arr = Array.isArray(character[key]) ? character[key].slice() : [];
                arr.splice(index, 1);
                character[key] = arr;
                saveCharacter();
            });
        $row.append($input).append($remove);
        $list.append($row);
    });
    $wrap.append($list);

    const $controls = $('<div></div>').addClass('solo-list-controls');
    const $add = $('<button type="button"></button>')
        .addClass('solo-list-add')
        .text(`+ Add ${label.toLowerCase()}`)
        .on('click', () => {
            const character = getCharacter();
            if (!character) return;
            const arr = Array.isArray(character[key]) ? character[key].slice() : [];
            arr.push('');
            character[key] = arr;
            saveCharacter();
        });
    $controls.append($add);

    // If the pack ships a vocabulary for this field, render a "Pick from
    // pack" dropdown that appends a chosen entry to the list. Free-text
    // entry stays available alongside.
    const usableGroups = Array.isArray(vocabularyGroups)
        ? vocabularyGroups.filter((g) => Array.isArray(g.entries) && g.entries.length > 0)
        : [];
    if (usableGroups.length > 0) {
        const $picker = $('<select></select>').addClass('solo-vocab-picker');
        $picker.append($('<option value=""></option>').text(`+ Pick from pack…`));
        for (const group of usableGroups) {
            const $og = $('<optgroup></optgroup>').attr('label', group.axis);
            for (const entry of group.entries) {
                $og.append($('<option></option>').attr('value', entry).text(entry));
            }
            $picker.append($og);
        }
        $picker.on('change', () => {
            const choice = String($picker.val() ?? '').trim();
            $picker.val('');
            if (!choice) return;
            const character = getCharacter();
            if (!character) return;
            const arr = Array.isArray(character[key]) ? character[key].slice() : [];
            // Skip duplicates — picking the same phrase twice is almost
            // always an accidental click.
            if (arr.some((existing) => existing.toLowerCase() === choice.toLowerCase())) {
                return;
            }
            arr.push(choice);
            character[key] = arr;
            saveCharacter();
        });
        $controls.append($picker);
    }
    $wrap.append($controls);
    return $wrap;
}

function renderRelationships(value) {
    const items = Array.isArray(value) ? value : [];
    const $wrap = $('<div></div>').addClass('solo-field solo-field-list');
    $wrap.append($('<label></label>').text('Relationships'));

    const $list = $('<ul></ul>').addClass('solo-list');
    items.forEach((item, index) => {
        const $row = $('<li></li>').addClass('solo-list-row');
        const $name = $('<input type="text" />').val(item?.name ?? '').attr('placeholder', 'Name');
        const $tie = $('<input type="text" />').val(item?.tie ?? '').attr('placeholder', 'Tie (mentor, sibling, debtor)');
        const commit = () => {
            const character = getCharacter();
            if (!character) return;
            const arr = Array.isArray(character.relationships) ? character.relationships.slice() : [];
            arr[index] = {
                name: String($name.val() ?? '').trim(),
                tie: String($tie.val() ?? '').trim(),
            };
            character.relationships = arr.filter((entry) => entry.name);
            saveCharacter({ rerender: false });
        };
        $name.on('change blur', commit);
        $tie.on('change blur', commit);
        const $remove = $('<button type="button" title="Remove"></button>')
            .addClass('solo-list-remove')
            .text('×')
            .on('click', () => {
                const character = getCharacter();
                if (!character) return;
                const arr = Array.isArray(character.relationships) ? character.relationships.slice() : [];
                arr.splice(index, 1);
                character.relationships = arr;
                saveCharacter();
            });
        $row.append($name).append($tie).append($remove);
        $list.append($row);
    });
    $wrap.append($list);

    const $add = $('<button type="button"></button>')
        .addClass('solo-list-add')
        .text('+ Add relationship')
        .on('click', () => {
            const character = getCharacter();
            if (!character) return;
            const arr = Array.isArray(character.relationships) ? character.relationships.slice() : [];
            arr.push({ name: '', tie: '' });
            character.relationships = arr;
            saveCharacter();
        });
    $wrap.append($add);
    return $wrap;
}

// ---- Chat-history excerpt used by debug views -------------------------

export function buildRecentChatExcerpt(limit = 8) {
    const context = getContext();
    const chat = Array.isArray(context.chat) ? context.chat : [];
    const tail = chat.slice(-Math.max(2, limit));
    return tail.map((m) => {
        const who = m.is_user ? 'Player' : (m.name || 'GM');
        const mes = String(m.mes ?? '').trim();
        return `${who}: ${mes}`;
    }).join('\n\n');
}
