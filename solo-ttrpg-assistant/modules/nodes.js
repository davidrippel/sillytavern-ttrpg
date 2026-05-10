import { loadCurrentLorebook } from './pack.js';

const NODE_KINDS = new Set(['location', 'npc_encounter', 'event']);

function entriesOf(lorebook) {
    if (!lorebook) return [];
    if (Array.isArray(lorebook.entries)) return lorebook.entries;
    if (lorebook.entries && typeof lorebook.entries === 'object') return Object.values(lorebook.entries);
    return [];
}

function parseListSection(content, sectionName) {
    const re = new RegExp(`^${sectionName}\\s*:\\s*$`, 'mi');
    const after = content.split(re)[1];
    if (!after) return [];
    const items = [];
    for (const rawLine of after.split('\n')) {
        const line = rawLine.trim();
        if (!line) continue;
        if (/^[a-z][\w\s]*:\s*/i.test(line) && !/^[-*•]/.test(line)) break;
        const bullet = line.match(/^[-*•]\s*(.+)$/);
        if (!bullet) continue;
        items.push(bullet[1].trim());
    }
    return items;
}

function parseInlineList(content, sectionName) {
    const re = new RegExp(`^${sectionName}\\s*:\\s*(.*)$`, 'mi');
    const m = content.match(re);
    if (!m) return [];
    const inline = m[1].trim();
    if (!inline) return parseListSection(content, sectionName);
    return inline.split(',').map((s) => s.trim()).filter(Boolean);
}

function parseNodeEntry(entry) {
    const comment = String(entry?.comment ?? '');
    const idMatch = comment.match(/^Node:\s*(.+)$/);
    if (!idMatch) return null;
    const id = idMatch[1].trim();

    const content = String(entry?.content ?? '');
    const kindRaw = (content.match(/^Kind:\s*(.+)$/m)?.[1] ?? '').trim().toLowerCase();
    const kind = NODE_KINDS.has(kindRaw) ? kindRaw : 'location';
    const description = (content.match(/^Description:\s*([\s\S]*?)(?:\n[A-Z][\w ]*:|$)/m)?.[1] ?? '').trim();

    const entryClues = parseInlineList(content, 'Entry clues');
    const exitClues = parseInlineList(content, 'Exit clues');
    const gating = parseInlineList(content, 'Gating');

    const underspecified = /^Underspecified:\s*true\s*$/im.test(content);
    const triggersText = (content.match(/^Triggers:\s*(.+)$/m)?.[1] ?? '').trim();
    const triggers = triggersText ? triggersText : null;

    return { id, kind, description, entryClues, exitClues, gating, triggers, underspecified, entry };
}

export async function loadAllNodes() {
    const lorebook = await loadCurrentLorebook();
    const nodes = [];
    for (const entry of entriesOf(lorebook)) {
        const parsed = parseNodeEntry(entry);
        if (parsed) nodes.push(parsed);
    }
    return nodes;
}

export function nodeExists(nodes, id) {
    return nodes.some((n) => n.id === id);
}

export async function isCampaignNodeMode() {
    const lorebook = await loadCurrentLorebook();
    for (const entry of entriesOf(lorebook)) {
        if (/^Node:\s*\S/.test(String(entry?.comment ?? ''))) return true;
    }
    return false;
}

export function discoveredCluesPointingToNodes(clues, discoveredIds) {
    const discovered = new Set(discoveredIds ?? []);
    const targets = new Set();
    for (const clue of clues) {
        if (!discovered.has(clue.id)) continue;
        for (const target of clue.pointsTo ?? []) {
            if (target.type === 'node' && target.value) targets.add(target.value);
        }
    }
    return targets;
}

function bootstrapPointedNodes(clues, nodes) {
    const pointedAt = new Set();
    for (const clue of clues) {
        for (const target of clue.pointsTo ?? []) {
            if (target.type === 'clue') pointedAt.add(target.value);
        }
    }
    const pointed = new Set();
    for (const clue of clues) {
        if (pointedAt.has(clue.id)) continue;
        for (const target of clue.pointsTo ?? []) {
            if (target.type === 'node' && target.value) pointed.add(target.value);
        }
    }
    if (pointed.size === 0) {
        for (const node of nodes) {
            if (!(node.gating ?? []).length) pointed.add(node.id);
        }
    }
    return pointed;
}

export function reachableNodes(nodes, clues, state, { maxResults = 8 } = {}) {
    const visited = new Set(state?.visitedNodes ?? []);
    const completed = new Set(state?.completedNodes ?? []);
    const discovered = state?.discoveredClues ?? [];

    const pointed = discoveredCluesPointingToNodes(clues, discovered);
    if (discovered.length === 0) {
        for (const id of bootstrapPointedNodes(clues, nodes)) pointed.add(id);
    }

    const result = [];
    for (const node of nodes) {
        if (completed.has(node.id)) continue;
        if (!pointed.has(node.id)) continue;
        const gatesUnmet = (node.gating ?? []).some((reqId) => !visited.has(reqId) && !completed.has(reqId));
        if (gatesUnmet) continue;
        result.push({
            id: node.id,
            kind: node.kind,
            description: node.description,
            visited: visited.has(node.id),
            underspecified: node.underspecified,
        });
        if (result.length >= maxResults) break;
    }
    return result;
}
