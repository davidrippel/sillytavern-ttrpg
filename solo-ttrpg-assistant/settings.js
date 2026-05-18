// settings.js — v3 flat settings panel driver.
//
// One panel, flat scroll, no nested submenus. Sections are collapsible
// <details> cards: Campaign, Character, Story, Director, Debug. The
// panel reads and writes the same `getSettings()` document as before;
// it just exposes the v3 surface (no stats, no abilities, no dice
// settings).
//
// Per-turn affordances (accept/reject fact, retire thread, open new
// thread) live in the inline UI under each message — NOT in this
// panel. The panel is for setup, review, and rare actions.

import { exportBackupBundle, importBackupBundle } from './modules/backup.js';
import {
    createCharacter,
    deleteCharacter,
    duplicateCharacter,
    getActiveCharacter,
    listCharacters,
    renameCharacter,
    setActiveCharacter,
    subscribeCharacters,
} from './modules/characters.js';
import { mountSheet } from './modules/sheet.js';
import { getActivePack, getLoadedPacks, parsePackFromFiles, setActivePack, storeLoadedPack, subscribePack } from './modules/pack.js';
import { getPersonaLinkInfo, promptPersonaLink } from './modules/persona_link.js';
import { getLogs, subscribeLog, log } from './modules/logger.js';
import { renderAuthorsNoteFromState } from './modules/authors_note.js';
import { rewindToTurn, appendProvisionalFacts, acceptFact } from './modules/facts.js';
import { openThread, retireThread, listAllActiveThreads } from './modules/threads.js';
import { refreshAllFactChips, renderThreadsTray } from './modules/inline_ui.js';
import { getExtensionPath } from './modules/constants.js';
import {
    ensureStoryStateShape,
    escapeHtml,
    freshStoryState,
    getContext,
    getSettings,
    isExtensionEnabled,
    newCharacterId,
    readStoryState,
    saveSettings,
    writeStoryState,
} from './modules/util.js';

let panelRoot = null;
let packFilesInput = null;
let backupFilesInput = null;
let sampleFilesInput = null;

export async function mountSettingsPanel() {
    const context = getContext();
    const html = await context.renderExtensionTemplateAsync(getExtensionPath(), 'ui/settings_panel');
    $('#extensions_settings2 .solo-ttrpg-assistant').remove();
    $('#extensions_settings2').append(html);
    panelRoot = $('#extensions_settings2 #solo-ttrpg-panel').last();
    if (panelRoot.length === 0) return;

    packFilesInput = panelRoot.find('#solo-pack-files').get(0);
    backupFilesInput = panelRoot.find('#solo-backup-file').get(0);
    sampleFilesInput = panelRoot.find('#solo-sample-file').get(0);
    configureDirectoryPicker(packFilesInput);

    wireToggles();
    wireCampaignCard();
    wireCharacterCard();
    wireStoryCard();
    wireDirectorCard();
    wireDebugCard();

    mountSheet(panelRoot.find('#solo-sheet-root'));
    refreshAll();

    subscribePack(refreshAll);
    subscribeCharacters(refreshAll);
    subscribeLog(refreshLogPane);

    // Story state changes happen frequently (every turn); re-render the
    // story card on a light cadence by listening to chat events.
    const ctxEvents = context.eventTypes ?? {};
    const refreshEvents = [
        ctxEvents.MESSAGE_RECEIVED,
        ctxEvents.MESSAGE_SENT,
        ctxEvents.CHAT_CHANGED,
    ].filter(Boolean);
    for (const evt of refreshEvents) {
        context.eventSource.on(evt, () => refreshStoryCard());
    }
}

function configureDirectoryPicker(input) {
    if (!input) return;
    input.setAttribute('webkitdirectory', '');
    input.setAttribute('directory', '');
    input.setAttribute('multiple', '');
}

function refreshAll() {
    refreshHeader();
    refreshCampaignCard();
    refreshCharacterCard();
    refreshStoryCard();
    refreshDirectorCard();
    refreshLogPane();
}

// ---- Header / enabled --------------------------------------------------

function wireToggles() {
    panelRoot.find('#solo-enabled').on('change', (e) => {
        getSettings().enabled = Boolean(e.target.checked);
        saveSettings();
        toastr.info(getSettings().enabled ? 'Solo TTRPG enabled.' : 'Solo TTRPG disabled.');
    });
}

function refreshHeader() {
    panelRoot.find('#solo-enabled').prop('checked', isExtensionEnabled());
    const pack = getActivePack();
    panelRoot.find('#solo-active-pack-label').text(pack ? `Pack: ${pack.displayName} v${pack.version}` : 'No pack loaded');
}

// ---- Campaign card -----------------------------------------------------

function wireCampaignCard() {
    panelRoot.find('#solo-pack-load').on('click', () => packFilesInput?.click());
    $(packFilesInput).on('change', handlePackLoad);
    panelRoot.find('#solo-pack-select').on('change', handlePackSwitch);
    panelRoot.find('#solo-backup-export').on('click', () => exportBackupBundle().catch((e) => toastr.error(e.message)));
    panelRoot.find('#solo-backup-import').on('click', () => backupFilesInput?.click());
    $(backupFilesInput).on('change', handleBackupImport);
}

async function handlePackLoad(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    try {
        const pack = await parsePackFromFiles(Array.from(files));
        await storeLoadedPack(pack);
        toastr.success(`Loaded ${pack.displayName} v${pack.version}`);
    } catch (error) {
        toastr.error(error.message);
        log(`Pack load failed: ${error.message}`, 'warn');
    } finally {
        event.target.value = '';
    }
}

async function handlePackSwitch(event) {
    const name = event.target.value;
    if (!name) return;
    try {
        await setActivePack(name);
    } catch (error) {
        toastr.error(error.message);
    }
}

async function handleBackupImport(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
        await importBackupBundle(file);
        toastr.success('Backup imported.');
    } catch (error) {
        toastr.error(error.message);
    } finally {
        event.target.value = '';
    }
}

function refreshCampaignCard() {
    const $sel = panelRoot.find('#solo-pack-select').empty();
    const packs = getLoadedPacks();
    const activeName = getSettings().activePackName;
    const names = Object.keys(packs);
    if (names.length === 0) {
        $sel.append($('<option value="">— No packs loaded —</option>'));
    } else {
        for (const name of names) {
            const pack = packs[name];
            $sel.append(
                $('<option></option>').attr('value', name).text(`${pack.displayName} v${pack.version}`),
            );
        }
        if (activeName) $sel.val(activeName);
    }

    const pack = getActivePack();
    panelRoot.find('#solo-pack-info').text(pack ? pack.description : 'Pick a pack directory to load.');
}

// ---- Character card ----------------------------------------------------

function wireCharacterCard() {
    panelRoot.find('#solo-character-select').on('change', async (e) => {
        await setActiveCharacter(e.target.value);
    });
    panelRoot.find('#solo-character-new').on('click', () => {
        createCharacter({ name: '' });
        toastr.info('Created new character.');
    });
    panelRoot.find('#solo-character-duplicate').on('click', () => {
        const active = getActiveCharacter();
        if (!active) {
            toastr.warning('No active character to duplicate.');
            return;
        }
        try {
            duplicateCharacter(active.id);
        } catch (error) {
            toastr.error(error.message);
        }
    });
    panelRoot.find('#solo-character-delete').on('click', async () => {
        const active = getActiveCharacter();
        if (!active) return;
        if (!globalThis.confirm(`Delete character "${active.name || 'unnamed'}"? This cannot be undone.`)) return;
        deleteCharacter(active.id);
    });
    panelRoot.find('#solo-character-rename-go').on('click', () => {
        const active = getActiveCharacter();
        if (!active) return;
        const next = String(panelRoot.find('#solo-character-rename').val() ?? '').trim();
        if (!next) return;
        renameCharacter(active.id, next);
        panelRoot.find('#solo-character-rename').val('');
    });
    panelRoot.find('#solo-persona-link').on('click', async () => {
        const active = getActiveCharacter();
        if (!active) return;
        try {
            await promptPersonaLink(active);
        } catch (error) {
            toastr.error(error.message);
        }
    });
    panelRoot.find('#solo-sample-import').on('click', () => sampleFilesInput?.click());
    $(sampleFilesInput).on('change', handleSampleCharactersImport);
}

async function handleSampleCharactersImport(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
        const text = await file.text();
        const payload = JSON.parse(text);
        const characters = extractSampleCharacters(payload);
        if (characters.length === 0) {
            toastr.warning('No characters found in that file. Expected a sample_characters.json from the campaign generator.');
            return;
        }
        const picked = await promptSampleCharacterChoice(characters);
        if (!picked) return;
        const created = createCharacterFromSample(picked);
        toastr.success(`Imported "${created.name || 'unnamed'}" from campaign pregens.`);
    } catch (error) {
        toastr.error(`Sample-characters import failed: ${error.message}`);
        log(`Sample-characters import failed: ${error.message}`, 'warn');
    } finally {
        event.target.value = '';
    }
}

/**
 * The campaign generator writes sample_characters.json as either the bare
 * SampleCharacterSet payload (`{characters: [...]}`) or as the stage cache
 * file with the same shape under a top-level key. Be permissive about
 * both.
 */
function extractSampleCharacters(payload) {
    if (!payload || typeof payload !== 'object') return [];
    if (Array.isArray(payload)) return payload.filter((c) => c && c.name);
    if (Array.isArray(payload.characters)) return payload.characters.filter((c) => c && c.name);
    if (payload.data && Array.isArray(payload.data.characters)) {
        return payload.data.characters.filter((c) => c && c.name);
    }
    return [];
}

async function promptSampleCharacterChoice(characters) {
    const context = getContext();
    const choices = characters.map((c, idx) => ({ value: String(idx), label: c.name || `(unnamed #${idx + 1})` }));

    // SillyTavern's Popup API supports a simple select-popup. Fall back to
    // a plain prompt if it isn't available (very old client builds).
    try {
        if (context.Popup?.show?.input) {
            const labels = choices.map((c) => `${c.value}: ${c.label}`).join('\n');
            const raw = await context.Popup.show.input(
                'Import pregenerated character',
                `Type the number of the character to import:\n\n${labels}`,
                '0',
            );
            if (raw === null || raw === undefined || raw === '') return null;
            const idx = Number(raw);
            return Number.isFinite(idx) && idx >= 0 && idx < characters.length ? characters[idx] : null;
        }
    } catch {
        // Fall through to native prompt.
    }
    const labels = choices.map((c) => `${c.value}: ${c.label}`).join('\n');
    const raw = globalThis.prompt(`Pick a character (0–${characters.length - 1}):\n\n${labels}`, '0');
    if (raw === null) return null;
    const idx = Number(raw);
    return Number.isFinite(idx) && idx >= 0 && idx < characters.length ? characters[idx] : null;
}

function createCharacterFromSample(sample) {
    const settings = getSettings();
    const concept = String(sample.concept ?? '').trim();
    const hook = String(sample.hook_into_campaign ?? sample.hook ?? '').trim();
    const combinedNotes = hook ? `Hook into the campaign: ${hook}` : '';

    const record = {
        id: newCharacterId(),
        name: String(sample.name ?? '').trim(),
        concept,
        advantages: arrayOfStrings(sample.advantages),
        disadvantages: arrayOfStrings(sample.disadvantages),
        belongings: arrayOfStrings(sample.belongings),
        relationships: arrayOfRelationships(sample.relationships),
        notes: combinedNotes,
        packName: settings.activePackName ?? null,
        personaKey: null,
    };
    settings.characters[record.id] = record;
    settings.activeCharacterId = record.id;
    saveSettings();
    log(`Imported sample character "${record.name || '(unnamed)'}".`);
    refreshAll();
    return record;
}

function arrayOfStrings(value) {
    if (!Array.isArray(value)) return [];
    return value.map((entry) => String(entry ?? '').trim()).filter(Boolean);
}

function arrayOfRelationships(value) {
    if (!Array.isArray(value)) return [];
    return value
        .map((entry) => ({
            name: String(entry?.name ?? '').trim(),
            tie: String(entry?.tie ?? entry?.description ?? '').trim(),
        }))
        .filter((entry) => entry.name);
}

function refreshCharacterCard() {
    const $sel = panelRoot.find('#solo-character-select').empty();
    const characters = listCharacters();
    const active = getActiveCharacter();
    if (characters.length === 0) {
        $sel.append($('<option value="">— No characters yet —</option>'));
    } else {
        for (const c of characters) {
            $sel.append(
                $('<option></option>').attr('value', c.id).text(c.name || '(unnamed)'),
            );
        }
        if (active) $sel.val(active.id);
    }
    const info = active ? getPersonaLinkInfo(active) : null;
    panelRoot.find('#solo-persona-status').text(info ? info.summary : '(no persona linked)');
}

// ---- Story card --------------------------------------------------------

function wireStoryCard() {
    panelRoot.find('#solo-rewind').on('click', async () => {
        const state = ensureStoryStateShape(readStoryState() ?? {});
        const raw = globalThis.prompt(`Rewind to which turn? (current: ${state.turn})`, String(Math.max(0, state.turn - 1)));
        if (raw === null) return;
        const target = Number(raw);
        if (!Number.isFinite(target) || target < 0) {
            toastr.warning('Enter a non-negative integer.');
            return;
        }
        await rewindToTurn(target);
        await renderAuthorsNoteFromState();
        refreshAllFactChips();
        renderThreadsTray();
        refreshStoryCard();
        toastr.info(`Rewound to turn ${target}.`);
    });

    panelRoot.find('#solo-reset-campaign').on('click', async () => {
        const confirmed = globalThis.confirm(
            'Reset campaign state for this chat?\n\n'
            + 'This wipes:\n'
            + '  • all facts and threads\n'
            + '  • the truths-revealed log\n'
            + '  • scene context and on-screen NPCs\n'
            + '  • the active director\'s note and pressure cue\n'
            + '  • the turn counter (back to 0)\n\n'
            + 'It does NOT touch the chat itself, the character sheet, or the lorebook. Continue?'
        );
        if (!confirmed) return;
        await writeStoryState(freshStoryState());
        await renderAuthorsNoteFromState();
        refreshAllFactChips();
        renderThreadsTray();
        refreshStoryCard();
        refreshDirectorCard();
        log('Campaign state reset to turn 0.', 'info');
        toastr.info('Campaign state reset.');
    });

    panelRoot.find('#solo-thread-add').on('click', async () => {
        const q = globalThis.prompt('New thread (open dramatic question):', '');
        if (!q) return;
        const state = ensureStoryStateShape(readStoryState() ?? {});
        await openThread({ question: q, turn: state.turn });
        renderThreadsTray();
        refreshStoryCard();
    });
}

function refreshStoryCard() {
    if (!panelRoot) return;
    const state = ensureStoryStateShape(readStoryState() ?? {});
    panelRoot.find('#solo-turn-label').text(`Turn: ${state.turn}`);

    // Threads
    const $threads = panelRoot.find('#solo-threads-list').empty();
    const threads = listAllActiveThreads(state);
    if (threads.length === 0) {
        $threads.append($('<li></li>').addClass('solo-empty').text('No threads yet.'));
    } else {
        for (const t of threads) {
            const $li = $('<li></li>').addClass('solo-list-row');
            $li.append($('<span></span>').text(`[${t.status}] ${t.question}`));
            $li.append(
                $('<button type="button" class="solo-list-remove" title="Retire">×</button>')
                    .on('click', async () => {
                        await retireThread(t.id);
                        refreshStoryCard();
                        renderThreadsTray();
                    }),
            );
            $threads.append($li);
        }
    }

    // Facts
    const $facts = panelRoot.find('#solo-facts-list').empty();
    const accepted = state.facts.filter((f) => f.status === 'accepted').slice(-12);
    if (accepted.length === 0) {
        $facts.append($('<li></li>').addClass('solo-empty').text('No accepted facts yet.'));
    } else {
        for (const f of accepted) {
            $facts.append($('<li></li>').text(`[t${f.turn}] ${f.text}`));
        }
    }

    // Truths
    const $truths = panelRoot.find('#solo-truths-list').empty();
    const truths = state.truthsRevealed ?? [];
    if (truths.length === 0) {
        $truths.append($('<li></li>').addClass('solo-empty').text('No campaign truths revealed yet.'));
    } else {
        for (const t of truths) {
            $truths.append($('<li></li>').text(`[t${t.turn}] ${t.truthId} — ${t.how ?? ''}`));
        }
    }

    // Scene
    const scene = state.scene ?? {};
    const sceneParts = [];
    if (scene.location) sceneParts.push(`Location: ${scene.location}.`);
    if (scene.tension) sceneParts.push(`Tension: ${scene.tension}.`);
    if (Array.isArray(scene.presentNpcIds) && scene.presentNpcIds.length > 0) {
        sceneParts.push(`Present: ${scene.presentNpcIds.join(', ')}.`);
    }
    panelRoot.find('#solo-scene').text(sceneParts.join(' ') || '(scene not set yet)');
}

// ---- Director card -----------------------------------------------------

function wireDirectorCard() {
    panelRoot.find('#solo-extractor-enabled').on('change', (e) => {
        getSettings().factExtractor.enabled = Boolean(e.target.checked);
        saveSettings();
    });
    panelRoot.find('#solo-ui-chips').on('change', (e) => {
        getSettings().ui.inlineFactChips = Boolean(e.target.checked);
        saveSettings();
        refreshAllFactChips();
    });
    panelRoot.find('#solo-ui-tray').on('change', (e) => {
        getSettings().ui.threadsTray = Boolean(e.target.checked);
        saveSettings();
        renderThreadsTray();
    });
    panelRoot.find('#solo-manual-fact-add').on('click', async () => {
        const text = String(panelRoot.find('#solo-manual-fact').val() ?? '').trim();
        if (!text) return;
        const state = ensureStoryStateShape(readStoryState() ?? {});
        const created = await appendProvisionalFacts(state.turn, [{ text, sourceQuote: text, entities: [] }]);
        for (const f of created) await acceptFact(f.id);
        panelRoot.find('#solo-manual-fact').val('');
        await renderAuthorsNoteFromState();
        refreshStoryCard();
        toastr.info('Fact added.');
    });
    panelRoot.find('#solo-an-rebuild').on('click', async () => {
        await renderAuthorsNoteFromState();
        toastr.info('Author\'s Note rebuilt.');
    });
}

function refreshDirectorCard() {
    if (!panelRoot) return;
    const settings = getSettings();
    panelRoot.find('#solo-extractor-enabled').prop('checked', settings.factExtractor?.enabled !== false);
    panelRoot.find('#solo-ui-chips').prop('checked', settings.ui?.inlineFactChips !== false);
    panelRoot.find('#solo-ui-tray').prop('checked', settings.ui?.threadsTray !== false);

    const state = ensureStoryStateShape(readStoryState() ?? {});
    const note = state.directorsNotes?.active;
    panelRoot.find('#solo-active-note').text(note ? `${note.text}${note.hint ? ` — hint: ${note.hint}` : ''}` : '(none)');

    const cue = state.pressureCue;
    panelRoot.find('#solo-pressure-cue').text(cue?.kind ? `${cue.kind}${cue.reason ? ` — ${cue.reason}` : ''}` : '(none)');
}

// ---- Debug card --------------------------------------------------------

function wireDebugCard() {
    panelRoot.find('#solo-log-clear').on('click', () => {
        getSettings().logs = [];
        saveSettings();
        refreshLogPane();
    });
    panelRoot.find('#solo-state-dump').on('click', () => {
        const state = readStoryState();
        log('State dump.', 'info', state);
        refreshLogPane();
    });
}

function refreshLogPane() {
    if (!panelRoot) return;
    const logs = getLogs() ?? [];
    const lines = logs.slice(-200).map((entry) => {
        const ts = entry?.timestamp ?? '';
        const level = entry?.level ?? 'info';
        const msg = entry?.message ?? '';
        const det = entry?.details ? `\n    ${typeof entry.details === 'string' ? entry.details : JSON.stringify(entry.details)}` : '';
        return `[${ts}] ${level.toUpperCase()} ${msg}${det}`;
    });
    panelRoot.find('#solo-log').text(lines.join('\n'));
}
