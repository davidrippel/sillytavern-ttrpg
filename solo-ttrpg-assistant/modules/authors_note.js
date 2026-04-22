import { AUTHORS_NOTE_SECTIONS } from './constants.js';
import { log } from './logger.js';
import { buildRecentChatExcerpt } from './sheet.js';
import { loadCurrentLorebook, saveLorebook } from './pack.js';
import { maybeHandleStatusUpdate } from './status_update.js';
import {
    escapeHtml,
    getContext,
    getSettings,
    readAuthorsNote,
    writeAuthorsNote,
} from './util.js';

function normalizeHeading(label) {
    return label.trim().toLowerCase();
}

export function parseAuthorsNoteSections(text = readAuthorsNote()) {
    const normalizedLabels = new Map(AUTHORS_NOTE_SECTIONS.map((label) => [normalizeHeading(label), label]));
    const sections = Object.fromEntries(AUTHORS_NOTE_SECTIONS.map((label) => [label, '']));

    let currentLabel = null;
    const lines = String(text ?? '').split('\n');

    for (const line of lines) {
        const headingMatch = line.match(/^([^:]+):\s*(.*)$/);
        const normalized = headingMatch ? normalizeHeading(headingMatch[1]) : null;
        if (normalized && normalizedLabels.has(normalized)) {
            currentLabel = normalizedLabels.get(normalized);
            sections[currentLabel] = headingMatch[2].trim();
            continue;
        }

        if (currentLabel) {
            sections[currentLabel] = `${sections[currentLabel]}\n${line}`.trim();
        }
    }

    return sections;
}

export function formatAuthorsNoteSections(sections) {
    return AUTHORS_NOTE_SECTIONS
        .map((label) => `${label}: ${String(sections[label] ?? '').trim()}`)
        .join('\n');
}

async function confirmAuthorsNoteUpdate(title, nextSections, reason) {
    const context = getContext();
    const nextText = formatAuthorsNoteSections(nextSections);
    const popup = new context.Popup(
        `<div class="solo-ttrpg-assistant solo-stack"><p>${escapeHtml(reason)}</p><label class="solo-stack"><span>Review Author's Note</span><textarea id="solo-an-edit" class="solo-code">${escapeHtml(nextText)}</textarea></label></div>`,
        context.POPUP_TYPE.TEXT,
        title,
        {
            okButton: 'Apply',
            cancelButton: 'Cancel',
            wide: true,
        },
    );

    const result = await popup.show();
    if (result !== context.POPUP_RESULT.AFFIRMATIVE) {
        return false;
    }

    const finalText = popup.dom?.querySelector?.('#solo-an-edit')?.value ?? nextText;
    await writeAuthorsNote(finalText);
    log(`Updated Author's Note via ${title}.`);
    return true;
}

async function generateRecentBeatsProposal() {
    const settings = getSettings();
    const excerpt = buildRecentChatExcerpt(settings.authorsNote.recentBeatsMessages ?? 8);

    if (!excerpt.trim()) {
        return '';
    }

    const prompt = [
        'Summarize the most recent scene beats into 2-3 short bullet points.',
        'Keep spoilers out.',
        'Return plain text bullets only.',
        '',
        excerpt,
    ].join('\n');

    try {
        const result = await getContext().generateQuietPrompt({ quietPrompt: prompt });
        return String(result ?? '').trim();
    } catch (error) {
        log('Recent beats generation failed.', 'warn', error.message);
        return '';
    }
}

export async function runSceneEndFlow() {
    const context = getContext();
    const lastMessage = context.chat?.[context.chat.length - 1];
    if (lastMessage && !lastMessage.is_user) {
        await maybeHandleStatusUpdate(lastMessage);
    }

    const current = parseAuthorsNoteSections();
    const recentBeats = await generateRecentBeatsProposal();
    const next = {
        ...current,
        'Recent beats': recentBeats || current['Recent beats'],
    };

    await confirmAuthorsNoteUpdate(
        'Scene End',
        next,
        'Review the proposed Recent beats update. You can edit before applying.',
    );
}

function incrementActHeader(text) {
    const match = String(text ?? '').match(/Act\s+(\d+)\s*:\s*(.+)/i);
    if (!match) {
        return text || 'Act 2: TBD';
    }
    return `Act ${Number(match[1]) + 1}: ${match[2]}`;
}

export async function runActTransitionFlow() {
    const context = getContext();
    const lorebook = await loadCurrentLorebook();
    const entries = Array.isArray(lorebook?.entries) ? lorebook.entries : lorebook?.entries ? Object.values(lorebook.entries) : [];
    const currentActEntry = entries.find((entry) => entry?.comment === 'Current Act');

    const currentSections = parseAuthorsNoteSections();
    const proposedCurrentAct = incrementActHeader(currentActEntry?.content ?? currentSections['Current Act']);
    const input = await context.Popup.show.input(
        'Act Transition',
        'Edit the next Current Act text before applying it to the lorebook and Author\'s Note.',
        proposedCurrentAct,
    );

    if (!input) {
        return;
    }

    const nextSections = {
        ...currentSections,
        'Current Act': input,
    };

    const accepted = await confirmAuthorsNoteUpdate(
        'Act Transition',
        nextSections,
        'This updates the Current Act section and then writes the same text into the lorebook entry named "Current Act".',
    );

    if (!accepted) {
        return;
    }

    if (currentActEntry) {
        currentActEntry.content = input;
        await saveLorebook(lorebook);
        log('Updated Current Act lorebook entry.');
    } else {
        toastr.warning('No lorebook entry named "Current Act" was found. The Author\'s Note was updated anyway.');
    }
}
