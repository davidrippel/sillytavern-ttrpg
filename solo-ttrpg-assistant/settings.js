import { exportBackupBundle, importBackupBundle } from './modules/backup.js';
import { runActTransitionFlow, runSceneEndFlow } from './modules/authors_note.js';
import {
    createCharacter,
    deleteCharacter,
    duplicateCharacter,
    getActiveCharacter,
    getActiveCharacterId,
    listCharacters,
    setActiveCharacter,
    subscribeCharacterMeta,
    subscribeCharacters,
} from './modules/characters.js';
import { getLogs, subscribeLog } from './modules/logger.js';
import { getActivePack, getLoadedPacks, parsePackFromFiles, runCompatibilityCheck, setActivePack, storeLoadedPack, subscribePack } from './modules/pack.js';
import { mountSheet, renderSheet } from './modules/sheet.js';
import { clearBusy, escapeHtml, getContext, getSettings, isExtensionEnabled, saveSettings, setBusy } from './modules/util.js';
import { getExtensionPath } from './modules/constants.js';

let settingsRoot = null;
let packInput = null;
let backupInput = null;

function ensureEnabledControls() {
    if (!settingsRoot) {
        return;
    }

    const enabled = isExtensionEnabled();
    applyEnabledUiState(enabled);
}

function applyEnabledUiState(enabled) {
    if (!settingsRoot) {
        return;
    }

    const $root = $(settingsRoot);
    const $toggle = $root.find('#solo-enabled-toggle');
    const selector = [
        '#solo-pack-load',
        '#solo-pack-reload',
        '#solo-pack-select',
        '#solo-character-select',
        '#solo-character-new',
        '#solo-character-duplicate',
        '#solo-character-delete',
        '#solo-backup-export',
        '#solo-backup-import',
        '#solo-scene-end',
        '#solo-act-transition',
    ].join(', ');

    $toggle
        .text(enabled ? 'Active' : 'Paused')
        .toggleClass('solo-enabled', enabled)
        .toggleClass('solo-disabled', !enabled)
        .attr('aria-pressed', enabled ? 'true' : 'false');
    $root.find(selector).prop('disabled', !enabled);
}

function ensurePickerModeElement() {
    return null;
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

    // These non-standard attributes are what make Chromium-based browsers show a folder picker.
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

    // File System Access API directory handles are async-iterable.
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

    const packOptions = Object.values(getLoadedPacks())
        .sort((a, b) => a.displayName.localeCompare(b.displayName))
        .map((entry) => `<option value="${escapeHtml(entry.name)}"${settings.activePackName === entry.name ? ' selected' : ''}>${escapeHtml(entry.displayName)} (${escapeHtml(entry.version)})</option>`)
        .join('');

    $select.html(packOptions || '<option value="">No packs loaded</option>');

    if (!pack) {
        $status.text('Unknown pack mode');
        $description.text('Load a pack to unlock the structured sheet, attribute rolls, and status field validation.');
        return;
    }

    $status.text(`${pack.displayName} ${pack.version}`);
    $description.text(pack.description || 'Pack loaded.');
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

function renderCharacterPicker() {
    if (!settingsRoot) {
        return;
    }

    const $root = $(settingsRoot);
    const $select = $root.find('#solo-character-select');
    const characters = listCharacters();
    const activeId = getActiveCharacterId();

    if (characters.length === 0) {
        $select.html('<option value="">No characters</option>');
        return;
    }

    const options = characters
        .map((character) => {
            const label = character.name?.trim() || 'Unnamed character';
            const selected = character.id === activeId ? ' selected' : '';
            return `<option value="${escapeHtml(character.id)}"${selected}>${escapeHtml(label)}</option>`;
        })
        .join('');
    $select.html(options);
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

function handleCharacterNew() {
    if (!isExtensionEnabled()) {
        return;
    }

    const settings = getSettings();
    createCharacter({ name: '', packName: settings.activePackName ?? null });
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
}

export async function mountSettingsPanel() {
    const context = getContext();
    const html = await context.renderExtensionTemplateAsync(getExtensionPath(), 'ui/settings_panel');
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

    $(settingsRoot).find('#solo-character-select').on('change', handleCharacterSwitch);
    $(settingsRoot).find('#solo-character-new').on('click', handleCharacterNew);
    $(settingsRoot).find('#solo-character-duplicate').on('click', handleCharacterDuplicate);
    $(settingsRoot).find('#solo-character-delete').on('click', handleCharacterDelete);

    $(settingsRoot).find('#solo-backup-export').on('click', () => exportBackupBundle().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-backup-import').on('click', () => backupInput.click());
    $(backupInput).on('change', handleBackupImport);
    $(settingsRoot).find('#solo-scene-end').on('click', () => runSceneEndFlow().catch((error) => toastr.error(error.message)));
    $(settingsRoot).find('#solo-act-transition').on('click', () => runActTransitionFlow().catch((error) => toastr.error(error.message)));

    mountSheet(
        $(settingsRoot).find('#solo-sheet-root').get(0),
        $(settingsRoot).find('#solo-sheet-mode').get(0),
    );

    subscribeLog(renderLogs);
    subscribePack(renderPackSummary);
    subscribeCharacters(renderCharacterPicker);
    subscribeCharacterMeta(renderCharacterPicker);
    ensureEnabledControls();
    renderPackSummary();
    renderCharacterPicker();
    renderLogs();
}
