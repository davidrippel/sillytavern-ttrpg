import { exportBackupBundle, importBackupBundle } from './modules/backup.js';
import { runActTransitionFlow, runSceneEndFlow } from './modules/authors_note.js';
import { getLogs, subscribeLog } from './modules/logger.js';
import { getActivePack, getLoadedPacks, parsePackFromFiles, runCompatibilityCheck, setActivePack, storeLoadedPack, subscribePack } from './modules/pack.js';
import { mountSheet } from './modules/sheet.js';
import { clearBusy, escapeHtml, getContext, getSettings, setBusy } from './modules/util.js';
import { getExtensionPath } from './modules/constants.js';

let settingsRoot = null;
let packInput = null;
let backupInput = null;

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

async function handlePackSwitch(event) {
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

export async function mountSettingsPanel() {
    const context = getContext();
    const html = await context.renderExtensionTemplateAsync(getExtensionPath(), 'ui/settings_panel');
    $('#extensions_settings2').append(html);

    settingsRoot = $('#extensions_settings2 .solo-ttrpg-assistant').last().get(0);
    packInput = $(settingsRoot).find('#solo-pack-input').get(0);
    backupInput = $(settingsRoot).find('#solo-backup-input').get(0);

    $(settingsRoot).find('#solo-pack-load').on('click', () => packInput.click());
    $(settingsRoot).find('#solo-pack-reload').on('click', () => packInput.click());
    $(settingsRoot).find('#solo-pack-select').on('change', handlePackSwitch);
    $(packInput).on('change', handlePackInput);

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
    renderPackSummary();
    renderLogs();
}
