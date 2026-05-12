import { loadCurrentLorebook } from './pack.js';

const NODE_KINDS = new Set(['location', 'npc_encounter', 'event']);

function entriesOf(lorebook) {
    if (!lorebook) return [];
    if (Array.isArray(lorebook.entries)) return lorebook.entries;
    if (lorebook.entries && typeof lorebook.entries === 'object') return Object.values(lorebook.entries);
    return [];
}

function parseInlineList(content, sectionName) {
    const re = new RegExp(`^${sectionName}\\s*:\\s*(.*)$`, 'mi');
    const m = content.match(re);
    if (!m) return [];
    const inline = m[1].trim();
    if (!inline) return [];
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

    const actNumberRaw = (content.match(/^Act:\s*(\d+)$/m)?.[1] ?? '').trim();
    const actNumber = actNumberRaw ? Number(actNumberRaw) : null;
    const isActStart = /^Act start:\s*true\s*$/im.test(content);
    const isActFinal = /^Act final:\s*true\s*$/im.test(content);
    const isVictory = /^Victory:\s*true\s*$/im.test(content);
    const triggersText = (content.match(/^Triggers:\s*(.+)$/m)?.[1] ?? '').trim();
    const triggers = triggersText ? triggersText : null;

    return {
        id,
        kind,
        description,
        entryClues,
        exitClues,
        gating,
        triggers,
        actNumber,
        isActStart,
        isActFinal,
        isVictory,
        entry,
    };
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

export function currentNodeId(state) {
    const visited = state?.visitedNodes ?? [];
    if (visited.length === 0) return null;
    return visited[visited.length - 1];
}

/**
 * The node the player is effectively "at" for reachability/clue purposes.
 * Falls back to the act-1 start node when nothing has been visited yet, so
 * that pre-visit renders still surface the opening clues and their targets.
 */
export function effectiveCurrentNodeId(nodes, state) {
    const fromState = currentNodeId(state);
    if (fromState) return fromState;
    const startNode = (nodes ?? []).find((n) => n.isActStart && n.actNumber === 1);
    return startNode ? startNode.id : null;
}

/**
 * Reachable nodes from the current state. A node is reachable if:
 *   - it's the target of a clue currently emitted from the current node, OR
 *   - it's the target of any clue the player has already discovered.
 * The act-1 start node is included by default at the very beginning of play
 * (when nothing has been visited yet).
 */
export function reachableNodes(nodes, clues, state, { maxResults = 8 } = {}) {
    const completed = new Set(state?.completedNodes ?? []);
    const visited = new Set(state?.visitedNodes ?? []);
    const discovered = new Set(state?.discoveredClues ?? []);
    const currentId = effectiveCurrentNodeId(nodes, state);

    const reachableIds = new Set();
    for (const clue of clues) {
        if (clue.foundAtNode === currentId && clue.pointsToNode) {
            reachableIds.add(clue.pointsToNode);
        }
        if (discovered.has(clue.id) && clue.pointsToNode) {
            reachableIds.add(clue.pointsToNode);
        }
    }

    const result = [];
    for (const node of nodes) {
        if (completed.has(node.id)) continue;
        if (!reachableIds.has(node.id)) continue;
        const gatesUnmet = (node.gating ?? []).some((reqId) => !visited.has(reqId) && !completed.has(reqId));
        if (gatesUnmet) continue;
        result.push({
            id: node.id,
            kind: node.kind,
            description: node.description,
            visited: visited.has(node.id),
        });
        if (result.length >= maxResults) break;
    }
    return result;
}
