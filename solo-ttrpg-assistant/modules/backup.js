import { bytesToString, createZip, downloadBlob, readZip, stringToBytes } from '../lib/zip.js';
import { getCurrentChatLorebookName, loadCurrentLorebook, saveLorebook } from './pack.js';
import { getCharacter, saveCharacter } from './sheet.js';
import { log } from './logger.js';
import {
    deepClone,
    getContext,
    getCurrentChatName,
    getSettings,
    readAuthorsNote,
    saveSettings,
    sha256Hex,
    slugify,
    timestampFilePart,
    writeAuthorsNote,
} from './util.js';

function stringifyJson(value) {
    return JSON.stringify(value, null, 2);
}

function getPackReference() {
    const settings = getSettings();
    const pack = settings.activePack;
    if (!pack) {
        return { pack_name: null, pack_version: null };
    }
    return {
        pack_name: pack.name,
        pack_version: pack.version,
        display_name: pack.displayName,
    };
}

async function buildBundleFiles() {
    const context = getContext();
    const lorebook = await loadCurrentLorebook();
    const authorsNote = readAuthorsNote();
    const extensionState = deepClone(getSettings());
    const character = deepClone(getCharacter());
    const chat = deepClone(context.chat ?? []);
    const summary = context.extensionSettings?.summarize?.summary ?? '';
    const packReference = getPackReference();

    const files = {
        'chat.jsonl': chat.map((message) => JSON.stringify(message)).join('\n'),
        'lorebook.json': stringifyJson(lorebook ?? {}),
        'authors_note.txt': authorsNote,
        'character_sheet.json': stringifyJson(character),
        'extension_settings.json': stringifyJson(extensionState),
        'summary.txt': String(summary ?? ''),
        'vector_store_export.json': stringifyJson({ rebuild_from_chat: true, exported: false }),
        'pack_reference.json': stringifyJson(packReference),
        'README.txt': [
            'Solo TTRPG Assistant backup bundle',
            '',
            'This bundle stores the active chat, lorebook, Author\'s Note, character sheet, and extension settings.',
            'Vector data is not exported directly. Rebuild from chat after import if needed.',
        ].join('\n'),
    };

    const manifest = {
        bundle_version: 1,
        exported_at: new Date().toISOString(),
        campaign_name: getCurrentChatName(),
        lorebook_name: getCurrentChatLorebookName(),
        extension_version: '0.1.0',
        checksums: {},
    };

    for (const [name, contents] of Object.entries(files)) {
        manifest.checksums[name] = await sha256Hex(stringToBytes(contents));
    }

    files['manifest.json'] = stringifyJson(manifest);
    return files;
}

export async function exportBackupBundle() {
    const files = await buildBundleFiles();
    const entries = Object.entries(files).map(([name, data]) => ({ name, data }));
    const blob = createZip(entries);
    const filename = `campaign_${slugify(getCurrentChatName())}_${timestampFilePart()}.zip`;
    downloadBlob(blob, filename);
    log(`Exported backup bundle ${filename}.`);
}

function parseChatJsonl(text) {
    return text
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => JSON.parse(line));
}

async function validateImportBundle(entries) {
    const required = [
        'manifest.json',
        'chat.jsonl',
        'lorebook.json',
        'authors_note.txt',
        'character_sheet.json',
        'extension_settings.json',
    ];

    for (const name of required) {
        if (!entries.has(name)) {
            throw new Error(`Bundle is missing ${name}.`);
        }
    }

    const manifest = JSON.parse(bytesToString(entries.get('manifest.json')));
    for (const [name, checksum] of Object.entries(manifest.checksums ?? {})) {
        if (!entries.has(name)) {
            throw new Error(`Manifest references missing file ${name}.`);
        }
        const actual = await sha256Hex(entries.get(name));
        if (actual !== checksum) {
            throw new Error(`Checksum mismatch for ${name}.`);
        }
    }

    return manifest;
}

async function replaceCurrentChat(messages) {
    const context = getContext();
    context.chat.length = 0;
    for (const message of messages) {
        context.chat.push(message);
    }
    await context.saveChat();
}

export async function importBackupBundle(file) {
    const context = getContext();
    const entries = await readZip(file);
    const manifest = await validateImportBundle(entries);

    const confirmed = await context.Popup.show.confirm(
        'Import Backup',
        'This will replace the current chat, lorebook, Author\'s Note, and character sheet. Proceed?',
    );
    if (confirmed !== context.POPUP_RESULT.AFFIRMATIVE) {
        return;
    }

    const previous = {
        chat: deepClone(context.chat ?? []),
        authorsNote: readAuthorsNote(),
        character: deepClone(getCharacter()),
        extensionState: deepClone(getSettings()),
        lorebook: await loadCurrentLorebook(),
    };

    try {
        const nextChat = parseChatJsonl(bytesToString(entries.get('chat.jsonl')));
        const nextLorebook = JSON.parse(bytesToString(entries.get('lorebook.json')));
        const nextAuthorsNote = bytesToString(entries.get('authors_note.txt'));
        const nextCharacter = JSON.parse(bytesToString(entries.get('character_sheet.json')));
        const nextExtensionSettings = JSON.parse(bytesToString(entries.get('extension_settings.json')));

        await replaceCurrentChat(nextChat);
        await writeAuthorsNote(nextAuthorsNote);
        getSettings().character = nextCharacter;
        Object.assign(getSettings(), nextExtensionSettings);
        saveSettings();
        saveCharacter();

        if (getCurrentChatLorebookName()) {
            await saveLorebook(nextLorebook);
        } else {
            toastr.warning('No active chat lorebook is bound. Lorebook data was read from the bundle but not written back.');
        }

        log(`Imported backup bundle from ${manifest.exported_at}.`);
    } catch (error) {
        await replaceCurrentChat(previous.chat);
        await writeAuthorsNote(previous.authorsNote);
        getSettings().character = previous.character;
        Object.assign(getSettings(), previous.extensionState);
        saveSettings();
        saveCharacter();
        if (previous.lorebook && getCurrentChatLorebookName()) {
            await saveLorebook(previous.lorebook);
        }
        throw error;
    }
}
