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
    const reveals = (content.match(/^Reveals:\s*(.+)$/m)?.[1] ?? '').trim();

    const pointsTo = [];
    const pointsBlock = content.split(/^Points to:\s*$/m)[1] ?? '';
    for (const line of pointsBlock.split('\n')) {
        const m = line.match(/^[-*•]\s*(\w+):\s*(.+)$/);
        if (!m) continue;
        pointsTo.push({ type: m[1].toLowerCase().trim(), value: m[2].trim() });
    }

    return { id, reveals, pointsTo };
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

export function reachableClues(clues, discoveredIds, { maxResults = 5 } = {}) {
    const discovered = new Set(discoveredIds ?? []);
    const byId = new Map(clues.map((c) => [c.id, c]));

    const seeds = new Set(discovered);
    if (seeds.size === 0) {
        for (const clue of clues) {
            if (clue.id.includes('seed') || clue.id.includes('entry')) seeds.add(clue.id);
        }
        if (seeds.size === 0 && clues.length > 0) {
            seeds.add(clues[0].id);
        }
    }

    const reachable = new Set();
    for (const seedId of seeds) {
        const seed = byId.get(seedId);
        if (!seed) continue;
        for (const target of seed.pointsTo) {
            if (target.type !== 'clue') continue;
            if (discovered.has(target.value)) continue;
            reachable.add(target.value);
        }
    }

    const result = [];
    for (const id of reachable) {
        const clue = byId.get(id);
        if (!clue) continue;
        const firstSentence = String(clue.reveals).split(/(?<=[.!?])\s/)[0] ?? '';
        const truncated = firstSentence.length > 120 ? `${firstSentence.slice(0, 117)}...` : firstSentence;
        result.push({ id, label: truncated });
        if (result.length >= maxResults) break;
    }
    return result;
}
