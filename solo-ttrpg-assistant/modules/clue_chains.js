import { loadCurrentLorebook } from './pack.js';

function entriesOf(lorebook) {
    if (!lorebook) return [];
    if (Array.isArray(lorebook.entries)) return lorebook.entries;
    if (lorebook.entries && typeof lorebook.entries === 'object') return Object.values(lorebook.entries);
    return [];
}

function parseClueEntry(entry) {
    const comment = String(entry?.comment ?? '');
    const idMatch = comment.match(/^Clue:\s*(.+)$/);
    if (!idMatch) return null;
    const id = idMatch[1].trim();

    const content = String(entry?.content ?? '');
    const hint = (content.match(/^Hint:\s*(.+)$/m)?.[1] ?? '').trim();
    const reveals = (content.match(/^Reveals:\s*(.+)$/m)?.[1] ?? '').trim();
    const foundAtNode = (content.match(/^Found at node:\s*(.+)$/m)?.[1] ?? '').trim();
    const pointsToNode = (content.match(/^Points to node:\s*(.+)$/m)?.[1] ?? '').trim();

    return { id, hint, reveals, foundAtNode, pointsToNode };
}

export async function loadAllClues() {
    const lorebook = await loadCurrentLorebook();
    const clues = [];
    for (const entry of entriesOf(lorebook)) {
        const parsed = parseClueEntry(entry);
        if (parsed) clues.push(parsed);
    }
    return clues;
}

export function clueExists(clues, id) {
    return clues.some((c) => c.id === id);
}

/**
 * Clues findable at the current node that haven't been discovered yet.
 * The GM should drop these into the scene during play.
 */
export function reachableClues(clues, discoveredIds, currentNodeId, { maxResults = 5 } = {}) {
    if (!currentNodeId) return [];
    const discovered = new Set(discoveredIds ?? []);
    const result = [];
    for (const clue of clues) {
        if (clue.foundAtNode !== currentNodeId) continue;
        if (discovered.has(clue.id)) continue;
        const label = clue.hint?.trim() ? clue.hint.trim() : fallbackLabelFromReveals(clue.reveals);
        result.push({ id: clue.id, label });
        if (result.length >= maxResults) break;
    }
    return result;
}

function fallbackLabelFromReveals(reveals) {
    const text = String(reveals ?? '').trim();
    if (!text) return '';
    const firstSentence = text.split(/(?<=[.!?])\s/)[0] ?? text;
    if (firstSentence.length <= 120) return firstSentence;
    const window = firstSentence.slice(0, 117);
    const lastBoundary = window.search(/[\s,;:—–-][^\s,;:—–-]*$/);
    const cut = lastBoundary > 60 ? window.slice(0, lastBoundary) : window;
    return `${cut.replace(/[\s,;:—–-]+$/, '')}…`;
}
