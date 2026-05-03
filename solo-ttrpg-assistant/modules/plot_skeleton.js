import { loadCurrentLorebook, saveLorebook } from './pack.js';
import { log } from './logger.js';

function entriesOf(lorebook) {
    if (!lorebook) return [];
    if (Array.isArray(lorebook.entries)) return lorebook.entries;
    if (lorebook.entries && typeof lorebook.entries === 'object') return Object.values(lorebook.entries);
    return [];
}

function parseActFromContent(content) {
    const text = String(content ?? '');
    const lines = text.split('\n');
    const headerMatch = text.match(/^Act\s+(\d+)\s*:\s*(.+)$/m);
    const actNumber = headerMatch ? Number(headerMatch[1]) : null;
    const title = headerMatch ? headerMatch[2].trim() : '';

    const beats = [];
    let inBeats = false;
    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (/^beats\s*:?$/i.test(line)) { inBeats = true; continue; }
        if (!inBeats) continue;
        if (!line) continue;
        const bullet = line.match(/^[-*•]\s*(.+)$/);
        if (!bullet) {
            if (/^[a-z]+\s*:/i.test(line)) inBeats = false;
            continue;
        }
        const body = bullet[1].trim();
        const labelled = body.match(/^(\d+\.\d+)\s+(.+)$/);
        if (labelled) {
            beats.push({ label: labelled[1], text: body });
        } else {
            beats.push({ label: String(beats.length + 1), text: body });
        }
    }
    return { actNumber, title, beats };
}

function isActEntry(entry) {
    const c = String(entry?.comment ?? '');
    return /^Current Act:|^Act\s+\d+:/.test(c);
}

function actNumberFromComment(comment) {
    const m = String(comment ?? '').match(/Act\s+(\d+):/);
    return m ? Number(m[1]) : null;
}

export async function loadAllActs() {
    const lorebook = await loadCurrentLorebook();
    const allEntries = entriesOf(lorebook);
    log(`loadAllActs: lorebook present=${!!lorebook}, total entries=${allEntries.length}`, 'info');
    if (allEntries.length > 0) {
        const sampleComments = allEntries.slice(0, 8).map((e) => String(e?.comment ?? '(no comment)')).join(' | ');
        log(`loadAllActs: first comments = ${sampleComments}`, 'info');
    }
    const entries = allEntries.filter(isActEntry);
    log(`loadAllActs: entries matching act regex = ${entries.length}`, 'info');
    const acts = [];
    for (const entry of entries) {
        const parsed = parseActFromContent(entry.content);
        const actNumber = parsed.actNumber ?? actNumberFromComment(entry.comment);
        if (actNumber == null) {
            log(`loadAllActs: skipped entry "${entry.comment}" — no act number found in content or comment.`, 'warn');
            continue;
        }
        acts.push({
            actNumber,
            title: parsed.title,
            beats: parsed.beats,
            entry,
            isCurrentAct: String(entry.comment ?? '').startsWith('Current Act:'),
        });
        log(`loadAllActs: parsed Act ${actNumber} "${parsed.title}" with ${parsed.beats.length} beats: ${parsed.beats.map((b) => b.label).join(', ')}`, 'info');
    }
    acts.sort((a, b) => a.actNumber - b.actNumber);
    return { lorebook, acts };
}

export async function getActByNumber(actNumber) {
    const { acts } = await loadAllActs();
    return acts.find((a) => a.actNumber === actNumber) ?? null;
}

export async function getCurrentActFromLorebook() {
    const { acts } = await loadAllActs();
    return acts.find((a) => a.isCurrentAct) ?? acts[0] ?? null;
}

export function findBeat(act, label) {
    if (!act) return null;
    return act.beats.find((b) => b.label === label) ?? null;
}

export function nextBeatLabel(act, label) {
    if (!act) return null;
    const idx = act.beats.findIndex((b) => b.label === label);
    if (idx < 0 || idx >= act.beats.length - 1) return null;
    return act.beats[idx + 1].label;
}

export function isLastBeatOfAct(act, label) {
    if (!act || act.beats.length === 0) return false;
    return act.beats[act.beats.length - 1].label === label;
}

export async function rewriteCurrentActLorebookEntry(targetActNumber) {
    const { lorebook, acts } = await loadAllActs();
    if (!lorebook) return false;

    const targetAct = acts.find((a) => a.actNumber === targetActNumber);
    if (!targetAct) {
        log(`Cannot advance to act ${targetActNumber}: no lorebook entry found.`, 'warn');
        return false;
    }

    const current = acts.find((a) => a.isCurrentAct);
    if (current && current.entry !== targetAct.entry) {
        current.entry.comment = `Act ${current.actNumber}: ${current.title}`;
        current.entry.constant = false;
    }

    targetAct.entry.comment = `Current Act: ${targetAct.title}`;
    targetAct.entry.constant = true;

    await saveLorebook(lorebook);
    log(`Promoted Act ${targetActNumber} to Current Act in lorebook.`);
    return true;
}
