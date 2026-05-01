import { exportBackupBundle, importBackupBundle } from './modules/backup.js';
import { runActTransitionFlow, runSceneEndFlow } from './modules/authors_note.js';
import {
    convertCharacterMode,
    createCharacter,
    createStoryCharacter,
    deleteCharacter,
    duplicateCharacter,
    getActiveCharacter,
    getActiveCharacterId,
    listCharacters,
    renameCharacter,
    setActiveCharacter,
    subscribeCharacterMeta,
    subscribeCharacters,
} from './modules/characters.js';
import { executeAbilityRoll, executeAttributeRoll, executeManualRoll } from './modules/dice.js';
import { getLogs, subscribeLog } from './modules/logger.js';
import { getActivePack, getLoadedPacks, parsePackFromFiles, runCompatibilityCheck, setActivePack, storeLoadedPack, subscribePack } from './modules/pack.js';
import { getPersonaLinkInfo, promptPersonaLink, syncPersonaLink } from './modules/persona_link.js';
import { mountSheet, renderSheet, subscribeSheetState } from './modules/sheet.js';
import { clearBusy, escapeHtml, formatSignedNumber, getContext, getSettings, isExtensionEnabled, saveSettings, setBusy } from './modules/util.js';
import { getExtensionPath } from './modules/constants.js';

let settingsRoot = null;
let packInput = null;
let backupInput = null;

function getCharacterTypeLabel(character) {
    return (character?.mode ?? 'pack') === 'story' ? 'Story-Based' : 'Stats-Based';
}

function getCharacterTypeIcon(character) {
    return (character?.mode ?? 'pack') === 'story' ? '📖' : '📊';
}

function getAbilityLabel(ability) {
    if (typeof ability === 'string') {
        return ability;
    }
    if (!ability || typeof ability !== 'object') {
        return '';
    }
    return ability.level ? `${ability.name ?? ''} (${ability.level})` : `${ability.name ?? ''}`;
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

function ensureEnabledControls() {
    if (!settingsRoot) {
        return;
    }

    applyEnabledUiState(isExtensionEnabled());
}

function applyEnabledUiState(enabled) {
    if (!settingsRoot) {
        return;
    }

    const $root = $(settingsRoot);
    const $toggle = $root.find('#solo-enabled-toggle');

    $toggle
        .text(enabled ? 'Active' : 'Paused')
        .toggleClass('solo-enabled', enabled)
        .toggleClass('solo-disabled', !enabled)
        .attr('aria-pressed', enabled ? 'true' : 'false');

    $root.find('.solo-requires-enabled').prop('disabled', !enabled);
}

function getPackPickerMode() {
    if (typeof window.showDirectoryPicker === 'function') {
        return 'directory';
    }

    if (typeof window.showOpenFilePicker === 'function') {
        return 'file-handles';
    }

    return 'file-input';
}

function configureDirectoryPicker(input) {
    if (!input) {
        return;
    }

    input.setAttribute('webkitdirectory', '');
    input.setAttribute('directory', '');
    input.setAttribute('mozdirectory', '');
    input.setAttribute('accept', '.yaml,.yml,.json');
    input.multiple = true;
    input.webkitdirectory = true;
    input.accept = '.yaml,.yml,.json';
}

async function readFilesFromDirectoryHandle(handle, relativePath = '') {
    const files = [];

    for await (const [name, entry] of handle.entries()) {
        const nextPath = relativePath ? `${relativePath}/${name}` : name;

        if (entry.kind === 'file') {
            const file = await entry.getFile();
            files.push(new File([file], file.name, {
                type: file.type,
                lastModified: file.lastModified,
            }));
            continue;
        }

        if (entry.kind === 'directory') {
            files.push(...await readFilesFromDirectoryHandle(entry, nextPath));
        }
    }

    return files;
}

async function openPackPicker() {
    const mode = getPackPickerMode();

    if (mode === 'directory') {
        const handle = await window.showDirectoryPicker({ id: 'solo-ttrpg-pack' });
        return readFilesFromDirectoryHandle(handle);
    }

    if (mode === 'file-handles') {
        const handles = await window.showOpenFilePicker({
            id: 'solo-ttrpg-pack-files',
            multiple: true,
            types: [
                {
                    description: 'Pack files',
                    accept: {
                        'application/json': ['.json'],
                        'application/x-yaml': ['.yaml', '.yml'],
                        'text/yaml': ['.yaml', '.yml'],
                        'text/plain': ['.yaml', '.yml'],
                    },
                },
            ],
        });

        const files = await Promise.all(handles.map((handle) => handle.getFile()));
        return files.map((file) => new File([file], file.name, {
            type: file.type,
            lastModified: file.lastModified,
        }));
    }

    return new Promise((resolve) => {
        const onChange = (event) => {
            packInput.removeEventListener('change', onChange);
            resolve([...(event.target.files ?? [])]);
        };

        packInput.addEventListener('change', onChange, { once: true });
        packInput.click();
    });
}

function buildCharacterOptionLabel(character) {
    const base = character.name?.trim() || 'Unnamed character';
    const icon = getCharacterTypeIcon(character);
    const type = getCharacterTypeLabel(character);
    const personaInfo = getPersonaLinkInfo(character);
    const personaSuffix = personaInfo.linkedName ? ` - ${personaInfo.linkedName}` : '';
    return `${icon} ${base} - ${type}${personaSuffix}`;
}

function renderPackSummary() {
    if (!settingsRoot) {
        return;
    }

    const settings = getSettings();
    const pack = getActivePack();
    const $root = $(settingsRoot);
    const $status = $root.find('#solo-pack-status');
    const $description = $root.find('#solo-pack-description');
    const $select = $root.find('#solo-pack-select');
    const $playStatus = $root.find('#solo-play-pack-status');
    const $playDescription = $root.find('#solo-play-pack-description');

    const packOptions = Object.values(getLoadedPacks())
        .sort((a, b) => a.displayName.localeCompare(b.displayName))
        .map((entry) => `<option value="${escapeHtml(entry.name)}"${settings.activePackName === entry.name ? ' selected' : ''}>${escapeHtml(entry.displayName)} (${escapeHtml(entry.version)})</option>`)
        .join('');

    $select.html(packOptions || '<option value="">No packs loaded</option>');

    if (!pack) {
        $status.text('No pack loaded');
        $description.text('Load a pack to unlock the structured sheet, attribute rolls, and status field validation.');
        $playStatus.text('No pack loaded');
        $playDescription.text('Load a pack to enable structured rolls and resource tracking.');
        return;
    }

    const label = `${pack.displayName} ${pack.version}`;
    $status.text(label);
    $description.text(pack.description || 'Pack loaded.');
    $playStatus.text(label);
    $playDescription.text(pack.description || 'Pack loaded.');
}

function renderLogs() {
    if (!settingsRoot) {
        return;
    }

    const html = getLogs().map((entry) => `
        <div class="solo-log-entry">
            <div class="solo-row spread">
                <strong>${escapeHtml(entry.message)}</strong>
                <span class="solo-muted">${escapeHtml(new Date(entry.timestamp).toLocaleString())}</span>
            </div>
            ${entry.details ? `<div class="solo-muted solo-code">${escapeHtml(typeof entry.details === 'string' ? entry.details : JSON.stringify(entry.details, null, 2))}</div>` : ''}
        </div>
    `).join('');

    $(settingsRoot).find('#solo-log-root').html(html || '<div class="solo-muted">No activity yet.</div>');
}

function renderCharacterPicker() {
    if (!settingsRoot) {
        return;
    }

    const $root = $(settingsRoot);
    const characters = listCharacters();
    const activeId = getActiveCharacterId();
    const $selects = $root.find('#solo-character-select, #solo-play-character-select');

    if (characters.length === 0) {
        $selects.html('<option value="">No characters</option>');
        return;
    }

    const options = characters
        .map((character) => {
            const selected = character.id === activeId ? ' selected' : '';
            return `<option value="${escapeHtml(character.id)}"${selected}>${escapeHtml(buildCharacterOptionLabel(character))}</option>`;
        })
        .join('');
    $selects.html(options);
}

function renderCharacterStatus() {
    if (!settingsRoot) {
        return;
    }

    const character = getActiveCharacter();
    const typeLabel = getCharacterTypeLabel(character);
    const typeIcon = getCharacterTypeIcon(character);
    const isStory = (character?.mode ?? 'pack') === 'story';

    const $root = $(settingsRoot);
    const $badge = $root.find('#solo-character-type-badge');
    $badge.text(`${typeIcon} ${typeLabel}`);
    $badge.toggleClass('solo-badge--story', !!character && isStory);
    $badge.toggleClass('solo-badge--stats', !!character && !isStory);
    $root.find('#solo-play-character-type').text(typeLabel);
    $root.find('#solo-character-convert').prop('disabled', !character);
}

function renderPlayConditions(character) {
    const $root = $(settingsRoot).find('#solo-play-conditions');
    $root.empty();

    if (!character) {
        return;
    }

    if ((character.mode ?? 'pack') === 'story') {
        const strengths = (character.strengths ?? []).filter(Boolean);
        if (strengths.length > 0) {
            $root.append(`<div class="solo-stack"><strong>Strengths</strong><div class="solo-pill-list">${strengths.map((value) => `<span class="solo-pill">${escapeHtml(value)}</span>`).join('')}</div></div>`);
        }
        if (character.weakness) {
            $root.append(`<div class="solo-stack"><strong>Weakness</strong><div class="solo-pill-list"><span class="solo-pill">${escapeHtml(character.weakness)}</span></div></div>`);
        }
        return;
    }

    const conditions = Array.isArray(character.state?.conditions) ? character.state.conditions.filter(Boolean) : [];
    if (conditions.length === 0) {
        return;
    }

    $root.append(`<div class="solo-stack"><strong>Conditions</strong><div class="solo-pill-list">${conditions.map((value) => `<span class="solo-pill">${escapeHtml(value)}</span>`).join('')}</div></div>`);
}

function renderPlayResources(character, pack) {
    const $root = $(settingsRoot).find('#solo-play-resources');
    $root.empty();

    if (!character) {
        $root.html('<div class="solo-muted">No active character.</div>');
        return;
    }

    if ((character.mode ?? 'pack') === 'story') {
        $root.append(`<div class="solo-summary-card"><strong>${escapeHtml(character.name || 'Story-Based Character')}</strong><span class="solo-muted">${escapeHtml(character.description || 'Outcomes resolve narratively. No dice or resource pools are active.')}</span></div>`);
        return;
    }

    if (!pack) {
        const entries = Object.entries(character.state ?? {});
        if (entries.length === 0) {
            $root.html('<div class="solo-muted">No state fields yet. Load a pack or edit the sheet to add fields.</div>');
            return;
        }

        for (const [key, value] of entries) {
            const rendered = Array.isArray(value) ? value.join(', ') : String(value ?? '');
            $root.append(`<div class="solo-summary-card"><strong>${escapeHtml(key)}</strong><span>${escapeHtml(rendered)}</span></div>`);
        }
        return;
    }

    for (const resource of pack.resources) {
        const value = getResourceDisplay(character, resource);
        const $card = $(`<div class="solo-summary-card"><strong>${escapeHtml(resource.display)}</strong><span>${escapeHtml(value)}</span></div>`);

        if (resource.kind === 'pool' || resource.kind === 'pool_with_threshold') {
            const maxKey = resource.max_value_field ?? resource.threshold_field;
            const maxValue = Number(character.state?.[maxKey] ?? 0) || 0;
            const currentValue = Number(character.state?.[resource.key] ?? 0) || 0;
            const ratio = maxValue > 0 ? Math.min(100, Math.max(0, (currentValue / maxValue) * 100)) : 0;
            $card.append(`<div class="solo-progress"><span style="width:${ratio}%"></span></div>`);
        }

        $root.append($card);
    }
}

function renderPlayRolls(character, pack) {
    const $rolls = $(settingsRoot).find('#solo-play-rolls');
    const $abilitySelect = $(settingsRoot).find('#solo-play-ability-select');
    const $abilityButton = $(settingsRoot).find('#solo-play-ability-roll');
    const $manualButton = $(settingsRoot).find('#solo-play-manual-roll');
    const $storyNote = $(settingsRoot).find('#solo-play-story-note');

    $rolls.empty();
    $storyNote.text('');

    if (!character) {
        $rolls.html('<div class="solo-muted">No active character.</div>');
        $abilitySelect.html('<option value="">No abilities</option>').prop('disabled', true);
        $abilityButton.prop('disabled', true);
        $manualButton.prop('disabled', true);
        return;
    }

    if ((character.mode ?? 'pack') === 'story') {
        $rolls.html('<div class="solo-muted">Story-based characters resolve outcomes narratively.</div>');
        $abilitySelect.html('<option value="">No abilities</option>').prop('disabled', true);
        $abilityButton.prop('disabled', true);
        $manualButton.prop('disabled', true);
        $storyNote.text('Story-based characters do not use attribute or ability rolls.');
        return;
    }

    $manualButton.prop('disabled', !isExtensionEnabled());

    if (!pack) {
        $rolls.html('<div class="solo-muted">Load a pack to enable attribute rolls.</div>');
        $abilitySelect.html('<option value="">No abilities</option>').prop('disabled', true);
        $abilityButton.prop('disabled', true);
        $storyNote.text('Manual rolls are still available without a pack.');
        return;
    }

    for (const attribute of pack.attributes) {
        const modifier = Number(character.attributes?.[attribute.key] ?? 0);
        const $button = $(`<button class="menu_button solo-requires-enabled" type="button">${escapeHtml(attribute.display)} ${escapeHtml(formatSignedNumber(modifier))}</button>`);
        $button.on('click', () => executeAttributeRoll(attribute.key).catch((error) => toastr.error(error.message)));
        $rolls.append($button);
    }

    const abilities = (character.abilities ?? [])
        .map((ability) => ({ value: typeof ability === 'string' ? ability : String(ability?.name ?? ''), label: getAbilityLabel(ability) }))
        .filter((ability) => ability.value);

    if (abilities.length === 0) {
        $abilitySelect.html('<option value="">No abilities on sheet</option>').prop('disabled', true);
        $abilityButton.prop('disabled', true);
        return;
    }

    $abilitySelect.html(abilities.map((ability) => `<option value="${escapeHtml(ability.value)}">${escapeHtml(ability.label)}</option>`).join(''));
    $abilitySelect.prop('disabled', !isExtensionEnabled());
    $abilityButton.prop('disabled', !isExtensionEnabled());
}

function renderPersonaSummary() {
    if (!settingsRoot) {
        return;
    }

    const character = getActiveCharacter();
    const info = getPersonaLinkInfo(character);
    $(settingsRoot).find('#solo-play-persona-state').text(info.label);
    $(settingsRoot).find('#solo-play-persona-meta').text(info.detail);
}

function renderPlayDashboard() {
    if (!settingsRoot) {
        return;
    }

    const character = getActiveCharacter();
    const pack = getActivePack();
    renderPersonaSummary();
    renderCharacterStatus();
    renderPlayResources(character, pack);
    renderPlayConditions(character);
    renderPlayRolls(character, pack);
    ensureEnabledControls();
}

async function handlePackInput(event) {
    if (!isExtensionEnabled()) {
        event.target.value = '';
        return;
    }

    const files = [...(event.target.files ?? [])];
    if (files.length === 0) {
        return;
    }

    const $button = $(settingsRoot).find('#solo-pack-load');
    setBusy($button, 'Loading...');

    try {
        const pack = await parsePackFromFiles(files);
        await storeLoadedPack(pack);
        renderPackSummary();
        renderPlayDashboard();
        await runCompatibilityCheck({ interactive: true });
        toastr.success(`Loaded pack ${pack.displayName}.`);
    } catch (error) {
        toastr.error(error.message);
    } finally {
        clearBusy($button);
        event.target.value = '';
    }
}

async function handlePackLoadClick() {
    if (!isExtensionEnabled()) {
        return;
    }

    const $button = $(settingsRoot).find('#solo-pack-load');
    setBusy($button, 'Loading...');

    try {
        const pickerMode = getPackPickerMode();
        if (pickerMode !== 'directory') {
            toastr.info('This browser is not exposing a folder picker here. Select the 5 required pack files: pack.yaml, attributes.yaml, resources.yaml, abilities.yaml, and character_template.json.');
        }

        const files = await openPackPicker();
        if (!files || files.length === 0) {
            return;
        }

        const pack = await parsePackFromFiles(files);
        await storeLoadedPack(pack);
        renderPackSummary();
        renderPlayDashboard();
        await runCompatibilityCheck({ interactive: true });
        toastr.success(`Loaded pack ${pack.displayName}.`);
    } catch (error) {
        if (error?.name !== 'AbortError') {
            toastr.error(error.message);
        }
    } finally {
        clearBusy($button);
        if (packInput) {
            packInput.value = '';
        }
    }
}

async function handleCharacterSwitch(event) {
    if (!isExtensionEnabled()) {
        return;
    }

    const id = event.target.value;
    if (!id) {
        return;
    }

    try {
        await setActiveCharacter(id);
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handleCharacterNew() {
    if (!isExtensionEnabled()) {
        return;
    }

    const context = getContext();
    const wrapper = document.createElement('div');
    wrapper.className = 'solo-ttrpg-assistant solo-stack';

    const intro = document.createElement('p');
    intro.textContent = 'Choose a character type. You can convert later, but conversion is lossy.';
    wrapper.append(intro);

    const label = document.createElement('label');
    label.className = 'solo-stack';
    const labelText = document.createElement('span');
    labelText.textContent = 'Type';
    label.append(labelText);

    const select = document.createElement('select');
    select.className = 'text_pole wide100p';
    const statsOpt = document.createElement('option');
    statsOpt.value = 'pack';
    statsOpt.textContent = '📊 Stats-Based — attributes, abilities, equipment (uses active pack)';
    statsOpt.selected = true;
    select.append(statsOpt);
    const storyOpt = document.createElement('option');
    storyOpt.value = 'story';
    storyOpt.textContent = '📖 Story-Based — description, strengths, weakness (no pack required)';
    select.append(storyOpt);
    label.append(select);
    wrapper.append(label);

    let chosenType = 'pack';
    select.addEventListener('change', () => {
        chosenType = select.value === 'story' ? 'story' : 'pack';
    });

    const popup = new context.Popup(wrapper, context.POPUP_TYPE.CONFIRM, '', {
        okButton: 'Create',
        cancelButton: 'Cancel',
    });
    const result = await popup.show();
    if (result !== context.POPUP_RESULT.AFFIRMATIVE) {
        return;
    }

    if (chosenType === 'story') {
        createStoryCharacter({ name: '' });
    } else {
        const settings = getSettings();
        createCharacter({ name: '', packName: settings.activePackName ?? null });
    }
}

async function handleCharacterConvert() {
    if (!isExtensionEnabled()) {
        return;
    }

    const active = getActiveCharacter();
    if (!active) {
        toastr.info('Select a character first.');
        return;
    }

    const currentMode = (active.mode ?? 'pack') === 'story' ? 'story' : 'pack';
    const nextMode = currentMode === 'story' ? 'pack' : 'story';
    const nextLabel = nextMode === 'story' ? 'Story-Based' : 'Stats-Based';
    const lossDescription = nextMode === 'story'
        ? 'attributes, abilities, equipment, and conditions'
        : 'strengths and weakness';

    const context = getContext();
    const confirmed = await context.Popup.show.confirm(
        `Convert "${active.name || 'Unnamed character'}" to ${nextLabel}?`,
        `This will discard ${lossDescription}. Description and notes are preserved.\n\nThis cannot be undone.`,
    );
    if (confirmed !== context.POPUP_RESULT.AFFIRMATIVE) {
        return;
    }

    try {
        convertCharacterMode(active.id, nextMode);
        renderPlayDashboard();
        toastr.success(`Character converted to ${nextLabel}.`);
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handleCharacterRename() {
    if (!isExtensionEnabled()) {
        return;
    }

    const active = getActiveCharacter();
    if (!active) {
        return;
    }

    const nextName = await getContext().Popup.show.input('Rename Character', 'Enter a new name:', active.name ?? '');
    if (nextName === null) {
        return;
    }

    renameCharacter(active.id, nextName.trim());
}

async function handleCharacterImportSamples(event) {
    if (!isExtensionEnabled()) {
        event.target.value = '';
        return;
    }

    const [file] = event.target.files ?? [];
    if (!file) {
        return;
    }

    try {
        const text = await file.text();
        const data = JSON.parse(text);
        const characters = Array.isArray(data?.characters) ? data.characters : [];
        if (characters.length === 0) {
            toastr.warning('No characters found in this file.');
            return;
        }

        const context = getContext();
        const settings = getSettings();
        const activePackName = settings.activePackName ?? data.pack_name ?? null;

        for (const sample of characters) {
            const archetype = sample?.archetype ?? 'Sample character';
            const hasStory = !!sample?.story;
            const hasStats = !!sample?.pack;

            const wrapper = document.createElement('div');
            wrapper.className = 'solo-ttrpg-assistant solo-stack';

            const heading = document.createElement('h4');
            heading.textContent = `Import "${archetype}"`;
            wrapper.append(heading);

            if (sample?.hook_into_campaign) {
                const hook = document.createElement('p');
                hook.textContent = sample.hook_into_campaign;
                wrapper.append(hook);
            }

            const label = document.createElement('label');
            label.className = 'solo-stack';
            const labelText = document.createElement('span');
            labelText.textContent = 'Import as';
            label.append(labelText);

            const select = document.createElement('select');
            select.className = 'text_pole wide100p';
            const skipOpt = document.createElement('option');
            skipOpt.value = 'skip';
            skipOpt.textContent = '⏭ Skip this character';
            skipOpt.selected = true;
            select.append(skipOpt);
            if (hasStats) {
                const statsOpt = document.createElement('option');
                statsOpt.value = 'stats';
                statsOpt.textContent = '📊 Stats-Based character';
                select.append(statsOpt);
            }
            if (hasStory) {
                const storyOpt = document.createElement('option');
                storyOpt.value = 'story';
                storyOpt.textContent = '📖 Story-Based character';
                select.append(storyOpt);
            }
            label.append(select);
            wrapper.append(label);

            let mode = 'skip';
            select.addEventListener('change', () => {
                mode = select.value;
            });

            const popup = new context.Popup(wrapper, context.POPUP_TYPE.CONFIRM, '', {
                okButton: 'Import',
                cancelButton: 'Cancel All',
            });
            const result = await popup.show();
            if (result !== context.POPUP_RESULT.AFFIRMATIVE) {
                break;
            }

            if (mode === 'story' && sample?.story) {
                createStoryCharacter({
                    name: sample.story.name ?? archetype,
                    description: sample.story.description ?? '',
                    strengths: sample.story.strengths ?? [],
                    weakness: sample.story.weakness ?? '',
                });
            } else if ((mode === 'stats' || mode === 'pack') && sample?.pack) {
                const created = createCharacter({
                    name: sample.pack.name ?? archetype,
                    packName: activePackName,
                });
                created.concept = sample.pack.concept ?? created.concept ?? '';
                if (sample.pack.attributes && typeof sample.pack.attributes === 'object') {
                    created.attributes = { ...(created.attributes ?? {}), ...sample.pack.attributes };
                }
                if (Array.isArray(sample.pack.abilities)) {
                    created.abilities = sample.pack.abilities.slice();
                }
                if (Array.isArray(sample.pack.equipment)) {
                    created.equipment = sample.pack.equipment.slice();
                }
                if (sample.pack.notes) {
                    created.notes = sample.pack.notes;
                }
                saveSettings();
            }
        }

        toastr.success('Sample import complete.');
    } catch (error) {
        toastr.error(`Failed to import samples: ${error.message}`);
    } finally {
        event.target.value = '';
    }
}

function handleCharacterDuplicate() {
    if (!isExtensionEnabled()) {
        return;
    }

    const id = getActiveCharacterId();
    if (!id) {
        toastr.info('Create a character first.');
        return;
    }

    duplicateCharacter(id);
}

async function handleCharacterDelete() {
    if (!isExtensionEnabled()) {
        return;
    }

    const active = getActiveCharacter();
    if (!active) {
        return;
    }

    const context = getContext();
    const confirmed = await context.Popup.show.confirm('Delete Character', `Delete "${active.name || 'Unnamed character'}"? This cannot be undone.`);
    if (confirmed !== context.POPUP_RESULT.AFFIRMATIVE) {
        return;
    }

    try {
        deleteCharacter(active.id);
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handlePackSwitch(event) {
    if (!isExtensionEnabled()) {
        return;
    }

    const value = event.target.value;
    if (!value) {
        return;
    }

    try {
        await setActivePack(value);
        renderPackSummary();
        renderPlayDashboard();
        await runCompatibilityCheck({ interactive: true });
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handleBackupImport(event) {
    if (!isExtensionEnabled()) {
        event.target.value = '';
        return;
    }

    const [file] = event.target.files ?? [];
    if (!file) {
        return;
    }

    try {
        await importBackupBundle(file);
        toastr.success('Backup imported.');
        renderPackSummary();
        renderPlayDashboard();
    } catch (error) {
        toastr.error(error.message);
    } finally {
        event.target.value = '';
    }
}

function handleEnabledToggle(event) {
    event.preventDefault();
    event.stopPropagation();

    const nextEnabled = !isExtensionEnabled();
    const settings = getSettings();
    settings.enabled = nextEnabled;
    applyEnabledUiState(nextEnabled);
    saveSettings();
    renderSheet();
    renderPlayDashboard();
}

async function handlePlayManualRoll() {
    if (!isExtensionEnabled()) {
        return;
    }

    const value = await getContext().Popup.show.input('Manual Roll', 'Enter a modifier for a 2d6 roll.', '0');
    if (value === null) {
        return;
    }

    const modifier = Number(value);
    if (!Number.isFinite(modifier)) {
        toastr.error('Modifier must be a number.');
        return;
    }

    try {
        await executeManualRoll(modifier);
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handlePlayAbilityRoll() {
    if (!isExtensionEnabled()) {
        return;
    }

    const abilityName = $(settingsRoot).find('#solo-play-ability-select').val();
    if (!abilityName) {
        return;
    }

    try {
        await executeAbilityRoll(String(abilityName));
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handlePersonaChange() {
    if (!isExtensionEnabled()) {
        return;
    }

    const character = getActiveCharacter();
    if (!character) {
        return;
    }

    try {
        await promptPersonaLink(character);
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handlePersonaSync() {
    if (!isExtensionEnabled()) {
        return;
    }

    const character = getActiveCharacter();
    if (!character) {
        return;
    }

    try {
        await syncPersonaLink(character);
        renderPersonaSummary();
    } catch (error) {
        toastr.error(error.message);
    }
}

export async function mountSettingsPanel() {
    const context = getContext();
    const html = await context.renderExtensionTemplateAsync(getExtensionPath(), 'ui/settings_panel');
    $('#extensions_settings2 .solo-ttrpg-assistant').remove();
    $('#extensions_settings2').append(html);

    settingsRoot = $('#extensions_settings2 .solo-ttrpg-assistant').last().get(0);
    packInput = $(settingsRoot).find('#solo-pack-input').get(0);
    backupInput = $(settingsRoot).find('#solo-backup-input').get(0);
    configureDirectoryPicker(packInput);

    $(settingsRoot).on('click', '#solo-enabled-toggle', handleEnabledToggle);
    $(settingsRoot).find('#solo-pack-load').on('click', () => handlePackLoadClick());
    $(settingsRoot).find('#solo-pack-reload').on('click', () => handlePackLoadClick());
    $(settingsRoot).find('#solo-pack-select').on('change', handlePackSwitch);
    $(packInput).on('change', handlePackInput);

    const samplesInput = $(settingsRoot).find('#solo-character-samples-input').get(0);

    $(settingsRoot).find('#solo-character-select, #solo-play-character-select').on('change', handleCharacterSwitch);
    $(settingsRoot).find('#solo-character-new').on('click', () => handleCharacterNew().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-character-convert').on('click', () => handleCharacterConvert().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-character-rename').on('click', () => handleCharacterRename().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-character-duplicate').on('click', handleCharacterDuplicate);
    $(settingsRoot).find('#solo-character-delete').on('click', () => handleCharacterDelete().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-character-import-samples').on('click', () => samplesInput?.click());
    $(samplesInput).on('change', handleCharacterImportSamples);

    $(settingsRoot).find('#solo-play-persona-change').on('click', () => handlePersonaChange().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-play-persona-sync').on('click', () => handlePersonaSync().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-play-manual-roll').on('click', () => handlePlayManualRoll().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-play-ability-roll').on('click', () => handlePlayAbilityRoll().catch((error) => toastr.error(error.message)));

    $(settingsRoot).find('#solo-backup-export').on('click', () => exportBackupBundle().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-backup-import').on('click', () => backupInput.click());
    $(backupInput).on('change', handleBackupImport);

    $(settingsRoot).find('#solo-scene-end, #solo-play-scene-end').on('click', () => runSceneEndFlow().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-act-transition, #solo-play-act-transition').on('click', () => runActTransitionFlow().catch((error) => toastr.error(error.message)));

    mountSheet(
        $(settingsRoot).find('#solo-sheet-root').get(0),
        $(settingsRoot).find('#solo-sheet-mode').get(0),
    );

    subscribeLog(renderLogs);
    subscribePack(() => {
        renderPackSummary();
        renderPlayDashboard();
    });
    subscribeCharacters(() => {
        renderCharacterPicker();
        renderCharacterStatus();
        renderPlayDashboard();
    });
    subscribeCharacterMeta(() => {
        renderCharacterPicker();
        renderCharacterStatus();
        renderPlayDashboard();
    });
    subscribeSheetState(() => renderPlayDashboard());

    renderPackSummary();
    renderCharacterPicker();
    renderCharacterStatus();
    renderPlayDashboard();
    renderLogs();
    ensureEnabledControls();
}
