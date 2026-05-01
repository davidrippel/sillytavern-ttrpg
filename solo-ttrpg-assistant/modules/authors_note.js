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
        `<div class="solo-ttrpg-assistant solo-stack"><p>${escapeHtml(reason)}</p><label class="solo-stack"><span>Review Author's Note</span><textarea id="solo-an-edit" class="solo-code" rows="24" style="min-height: 60vh; width: 100%;">${escapeHtml(nextText)}</textarea></label></div>`,
        context.POPUP_TYPE.TEXT,
        title,
        {
            okButton: 'Apply',
            cancelButton: 'Cancel',
            wide: true,
            large: true,
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

function sanitizeProposal(raw, { requireBullets = true } = {}) {
    const text = String(raw ?? '').trim();
    if (!text) {
        return '';
    }

    const sectionHeadingPattern = new RegExp(
        `^\\s*(?:${AUTHORS_NOTE_SECTIONS.map((label) => label.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')).join('|')})\\s*:`,
        'i',
    );
    const isBullet = (line) => /^\s*[-*•]\s+/.test(line);
    const sentinelPattern = /^\(.*\)$/;

    const cleaned = [];
    for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (sectionHeadingPattern.test(trimmed)) {
            break;
        }
        if (/^---+\s*$/.test(trimmed)) {
            break;
        }
        if (/^\*\*[^*]+\*\*\s*[:?]/.test(trimmed)) {
            break;
        }
        cleaned.push(line);
    }

    const result = cleaned.join('\n').trim();
    if (!result) {
        return '';
    }

    if (requireBullets) {
        const lines = result.split('\n').map((line) => line.trim()).filter(Boolean);
        if (lines.length === 1 && sentinelPattern.test(lines[0])) {
            return result;
        }
        const bulletCount = lines.filter(isBullet).length;
        if (bulletCount === 0 || bulletCount < lines.length / 2) {
            log('Discarded malformed proposal (no bullet structure detected).', 'warn');
            return '';
        }
        const bulletsOnly = lines.filter(isBullet).join('\n');
        return bulletsOnly;
    }

    return result;
}

async function runQuietPrompt(prompt, label) {
    try {
        const result = await getContext().generateQuietPrompt({ quietPrompt: prompt });
        return sanitizeProposal(result);
    } catch (error) {
        log(`${label} generation failed.`, 'warn', error.message);
        return '';
    }
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
        '',
        'Output format — STRICT:',
        '- 2-3 short plain-text bullets, one beat per line.',
        '- Nothing else. No headings. No narration. No story continuation. No "---" separators. No NPC dialogue.',
        '',
        '=== Recent chat ===',
        excerpt,
    ].join('\n');

    return runQuietPrompt(prompt, 'Recent beats');
}

async function readCurrentActBeats() {
    const lorebook = await loadCurrentLorebook();
    const entries = Array.isArray(lorebook?.entries)
        ? lorebook.entries
        : lorebook?.entries
            ? Object.values(lorebook.entries)
            : [];
    const entry = entries.find((item) => item?.comment === 'Current Act');
    return String(entry?.content ?? '').trim();
}

async function generatePendingBeatsProposal(currentPendingBeats, recentBeatsSummary) {
    const actText = await readCurrentActBeats();

    if (!actText && !currentPendingBeats?.trim()) {
        return '';
    }

    const prompt = [
        'You diff authored act beats against what has happened in the story so far.',
        '',
        'For each beat in the Current Act lorebook entry, decide:',
        '- ADDRESSED: the beat\'s subject matter appears in either "Recent beats" or in any previously-addressed beat that has dropped off the Pending list. The player has reached the situation the beat describes — even if a choice within it is technically still open.',
        '- PENDING: the beat\'s subject matter has NOT yet appeared in Recent beats and is NOT yet in play.',
        '',
        'Important: a beat phrased as "X must decide whether to Y" is ADDRESSED once X is in the situation requiring the decision (e.g., the invitation arrived and was read). Do not keep it pending just because the choice itself is unmade.',
        '',
        'Output format — STRICT:',
        '- One bullet per PENDING beat, copied verbatim from the lorebook (keep the beat number prefix like "1.2").',
        '- EVERY non-empty line MUST start with "- ".',
        '- Nothing else. No headings. No explanations. No narration. No story continuation. No "---" separators. No NPC dialogue.',
        '- If every beat is addressed, return exactly: (all beats resolved)',
        '',
        '=== Current Act lorebook entry (authored beats) ===',
        actText || '(empty)',
        '',
        '=== Previously listed Pending beats ===',
        currentPendingBeats?.trim() || '(empty)',
        '',
        '=== Recent beats (what has actually happened) ===',
        recentBeatsSummary?.trim() || '(empty)',
    ].join('\n');

    return runQuietPrompt(prompt, 'Pending beats');
}

async function generateActiveThreadsProposal(currentActiveThreads) {
    const settings = getSettings();
    const excerpt = buildRecentChatExcerpt(settings.authorsNote.recentBeatsMessages ?? 8);

    if (!excerpt.trim() && !currentActiveThreads?.trim()) {
        return '';
    }

    const prompt = [
        'You track emergent active threads — open subplots, dangling NPC questions,',
        'unfulfilled promises, looming dangers — based on what has actually happened in chat.',
        'Carry forward threads still open, drop threads that resolved, add new ones that emerged.',
        '',
        'Output format — STRICT:',
        '- 2-5 short plain-text bullets, one thread per line.',
        '- Each bullet is one sentence, under 30 words.',
        '- Nothing else. No headings. No explanations. No narration. No story continuation. No "---" separators. No NPC dialogue blocks. Do NOT continue the scene.',
        '',
        '=== Previously listed Active threads ===',
        currentActiveThreads?.trim() || '(empty)',
        '',
        '=== Recent chat ===',
        excerpt || '(no chat yet)',
    ].join('\n');

    return runQuietPrompt(prompt, 'Active threads');
}

async function generateRemindersProposal(currentReminders) {
    const settings = getSettings();
    const excerpt = buildRecentChatExcerpt(settings.authorsNote.recentBeatsMessages ?? 8);

    if (!excerpt.trim() && !currentReminders?.trim()) {
        return '';
    }

    const prompt = [
        'You are tracking SITUATIONAL reminders the GM must not forget right now —',
        'short-term pressures the player has created or encountered:',
        'active countdowns, locked doors, NPC conditions (wounded, suspicious, captive),',
        'environmental hazards (storm closing in, fire spreading), unresolved promises the player made,',
        'time-sensitive offers, things hidden on the player\'s person.',
        '',
        'Rules:',
        '- Carry forward reminders from the previous list that are still in effect.',
        '- Drop reminders that have resolved or expired.',
        '- Add new reminders only when chat clearly establishes them.',
        '- Do NOT invent pressures the chat has not shown.',
        '- Do NOT include genre tone notes ("keep dread cold") — those belong elsewhere.',
        '- Do NOT include authored plot beats — those live in Pending beats.',
        '',
        'Output format — STRICT:',
        '- 0-5 short plain-text bullets, one reminder per line.',
        '- Nothing else. No headings (do NOT write "Reminders:"). No explanations. No narration. No story continuation. No "---" separators. No NPC dialogue.',
        '- If nothing situational is currently in play, return exactly: (none)',
        '',
        '=== Previously listed Reminders ===',
        currentReminders?.trim() || '(empty)',
        '',
        '=== Recent chat ===',
        excerpt || '(no chat yet)',
    ].join('\n');

    return runQuietPrompt(prompt, 'Reminders');
}

async function generateActOpeningBeatsProposal(newActText) {
    if (!newActText?.trim()) {
        return '';
    }

    const prompt = [
        'A new act is beginning. Below is the new Current Act text.',
        'List the pending beats for this NEW act as 2-5 short plain-text bullets, no headings, no spoilers about later acts.',
        'These are the beats the player has not yet encountered.',
        '',
        '=== New Current Act ===',
        newActText,
    ].join('\n');

    return runQuietPrompt(prompt, 'Pending beats (new act)');
}

export async function runSceneEndFlow() {
    const context = getContext();
    const lastMessage = context.chat?.[context.chat.length - 1];
    if (lastMessage && !lastMessage.is_user) {
        await maybeHandleStatusUpdate(lastMessage);
    }

    const current = parseAuthorsNoteSections();
    const recentBeats = await generateRecentBeatsProposal();
    const recentBeatsForDiff = recentBeats || current['Recent beats'];
    const [pendingBeats, activeThreads, reminders] = await Promise.all([
        generatePendingBeatsProposal(current['Pending beats'], recentBeatsForDiff),
        generateActiveThreadsProposal(current['Active threads']),
        generateRemindersProposal(current['Reminders']),
    ]);
    const next = {
        ...current,
        'Recent beats': recentBeats || current['Recent beats'],
        'Pending beats': pendingBeats || current['Pending beats'],
        'Active threads': activeThreads || current['Active threads'],
        'Reminders': reminders || current['Reminders'],
    };

    await confirmAuthorsNoteUpdate(
        'Scene End',
        next,
        'Review the proposed Recent beats, Pending beats, Active threads, and Reminders. You can edit before applying.',
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

    const [newPendingBeats, newActiveThreads] = await Promise.all([
        generateActOpeningBeatsProposal(input),
        generateActiveThreadsProposal(currentSections['Active threads']),
    ]);

    const nextSections = {
        ...currentSections,
        'Current Act': input,
        'Pending beats': newPendingBeats || currentSections['Pending beats'],
        'Active threads': newActiveThreads || currentSections['Active threads'],
    };

    const accepted = await confirmAuthorsNoteUpdate(
        'Act Transition',
        nextSections,
        'Updates the Current Act, Pending beats, and Active threads. The Current Act text is also written into the lorebook entry named "Current Act".',
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
