import { log } from './logger.js';
import { getContext, readStoryState, ensureStoryStateShape, safeJsonParse, getSettings } from './util.js';
import { loadAllClues, reachableClues } from './clue_chains.js';
import {
    loadAllNodes,
    isCampaignNodeMode,
    effectiveCurrentNodeId,
    reachableNodes,
} from './nodes.js';

const ANALYZER_SYSTEM_PROMPT = [
    'You are a state classifier for a tabletop RPG engine.',
    'You are NOT a game master. You do NOT narrate, write fiction, or roleplay.',
    'You read the provided GM narration plus a list of candidate clues and nodes.',
    'You decide which clues were genuinely revealed and whether the scene transitioned to a new node.',
    'Output STRICT JSON only — no prose, no markdown fences, no comments.',
    'Never invent ids: pick only from the lists provided. If nothing matches, return empty/null fields.',
].join(' ');

const MAX_CLUES_PER_TURN = 3;

function buildAnalyzerPrompt({ messageText, userTurnText, currentNode, reachable, available }) {
    const reachableLines = reachable.map((n) => `- id: ${n.id} | kind: ${n.kind} | desc: ${truncate(n.description, 220)}`);
    const availableLines = available.map((c) => `- id: ${c.id} | hint: ${truncate(c.hint, 120)} | reveals: ${truncate(c.reveals, 300)}`);

    const currentLine = currentNode
        ? `- id: ${currentNode.id} | kind: ${currentNode.kind} | desc: ${truncate(currentNode.description, 220)}`
        : '(none yet — campaign is at the act start)';

    return [
        'GM narration to classify (the most recent assistant turn):',
        '"""',
        String(messageText ?? '').trim(),
        '"""',
        '',
        'Player input that preceded it (for context only — do not classify it):',
        '"""',
        String(userTurnText ?? '').trim() || '(none)',
        '"""',
        '',
        'Current node:',
        currentLine,
        '',
        'Reachable nodes (the player may transition to one of these):',
        reachableLines.length ? reachableLines.join('\n') : '(none)',
        '',
        'Available clues at the current node (only these are candidates for "found"):',
        availableLines.length ? availableLines.join('\n') : '(none)',
        '',
        'Rules:',
        '- A clue is "found" only when the substance of its `reveals` text appears in the narration (paraphrase OK). Mentioning the NPC, location, or topic is NOT enough. Quote the supporting sentence from the narration as `evidence`.',
        '- A node is "visited" when the player has arrived at / engaged with it per kind: location = arrived + engaged with the place; npc_encounter = interacted with the NPC; event = the event has begun to land on the player.',
        '- A node is "complete" only when: location = at least one exit clue was surfaced; npc_encounter = something changed (attitude shift, secret revealed, decision made); event = the consequence has landed in fiction.',
        '- Choose at most one id for `node_visited` and at most one id for `node_completed`. The `node_completed` id may equal the current node id (the player just finished it). Both can be null.',
        '- `clues_found` may be empty. Do not include more than 3 entries.',
        '- Do not output anything other than the JSON object below.',
        '',
        'Output schema:',
        '{',
        '  "clues_found": [{ "id": "<clue id from Available clues>", "evidence": "<short quoted sentence from the narration>" }],',
        '  "node_visited": "<node id from Reachable nodes>" | null,',
        '  "node_completed": "<node id from Reachable nodes or the current node>" | null,',
        '  "notes": "<one short line of reasoning>"',
        '}',
    ].join('\n');
}

function truncate(text, max) {
    const s = String(text ?? '').trim();
    if (s.length <= max) return s;
    return `${s.slice(0, max - 1)}…`;
}

function extractJsonBlock(raw) {
    const text = String(raw ?? '').trim();
    if (!text) return null;
    // Strip markdown code fences if the model wrapped JSON.
    const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    const body = fenced ? fenced[1] : text;
    const first = body.indexOf('{');
    const last = body.lastIndexOf('}');
    if (first < 0 || last < first) return null;
    const sliced = body.slice(first, last + 1);
    return safeJsonParse(sliced, null);
}

function normalizeForFingerprint(text) {
    return String(text ?? '')
        .toLowerCase()
        .replace(/[\s]+/g, ' ')
        .replace(/[‘’‚‛]/g, "'")
        .replace(/[“”„‟]/g, '"')
        .replace(/[–—]/g, '-')
        .trim();
}

function evidenceMatches(evidence, prose) {
    const e = normalizeForFingerprint(evidence);
    if (!e || e.length < 6) return false;
    const p = normalizeForFingerprint(prose);
    if (p.includes(e)) return true;
    // Permit a slightly shorter substring match — the model often quotes loosely.
    if (e.length > 30) {
        const head = e.slice(0, 30);
        if (p.includes(head)) return true;
    }
    return false;
}

async function runAnalyzerLLM(prompt) {
    const context = getContext();
    const generate = context.generateRaw;
    if (typeof generate !== 'function') {
        log('Scene analyzer skipped — generateRaw unavailable.', 'warn');
        return '';
    }
    try {
        const result = await generate({
            prompt,
            systemPrompt: ANALYZER_SYSTEM_PROMPT,
            instructOverride: true,
        });
        return String(result ?? '');
    } catch (error) {
        log('Scene analyzer LLM call failed.', 'warn', error.message);
        return '';
    }
}

/**
 * Build the analyzer context bundle from current state + lorebook.
 * Exported for the manual "Run analysis" button so it can short-circuit when
 * there is nothing to classify (no available clues AND no reachable nodes).
 */
export async function buildAnalyzerContext() {
    const [clues, nodes] = await Promise.all([loadAllClues(), loadAllNodes()]);
    const state = ensureStoryStateShape(readStoryState());
    const currentId = effectiveCurrentNodeId(nodes, state);
    const currentNode = nodes.find((n) => n.id === currentId) ?? null;

    const reachable = reachableNodes(nodes, clues, state, { maxResults: 12, includeLatent: false });

    // Available clues = undiscovered clues found at the current node.
    const discovered = new Set(state.discoveredClues ?? []);
    const available = [];
    for (const clue of clues) {
        if (clue.foundAtNode !== currentId) continue;
        if (discovered.has(clue.id)) continue;
        available.push({ id: clue.id, hint: clue.hint, reveals: clue.reveals });
    }

    return { clues, nodes, state, currentNode, reachable, available };
}

/**
 * Run the analyzer LLM against the assistant prose and return validated decisions.
 *
 * @param {{ messageText: string, userTurnText?: string }} args
 * @returns {Promise<{
 *   clueIds: string[],
 *   nodeVisitedId: string | null,
 *   nodeCompletedId: string | null,
 *   notes: string,
 *   raw: string,
 *   ranLLM: boolean,
 * }>}
 */
export async function analyzeAssistantMessage({ messageText, userTurnText = '' }) {
    const empty = { clueIds: [], nodeVisitedId: null, nodeCompletedId: null, notes: '', raw: '', ranLLM: false };

    const prose = String(messageText ?? '').trim();
    if (!prose) return empty;

    if (!(await isCampaignNodeMode())) {
        return empty;
    }

    const { currentNode, reachable, available } = await buildAnalyzerContext();

    // Short-circuit: nothing the analyzer could decide.
    if (available.length === 0 && reachable.length === 0) {
        return empty;
    }

    const prompt = buildAnalyzerPrompt({
        messageText: prose,
        userTurnText,
        currentNode,
        reachable,
        available,
    });

    const raw = await runAnalyzerLLM(prompt);
    if (!raw.trim()) return { ...empty, ranLLM: true };

    const parsed = extractJsonBlock(raw);
    if (!parsed || typeof parsed !== 'object') {
        const preview = raw.slice(0, 240).replace(/\n/g, ' ⏎ ');
        log(`Scene analyzer: could not parse JSON. Raw: ${preview}`, 'warn');
        return { ...empty, raw, ranLLM: true };
    }

    const availableIds = new Set(available.map((c) => c.id));
    const reachableIds = new Set(reachable.map((n) => n.id));

    // --- clues ---
    const clueIds = [];
    const cluesRaw = Array.isArray(parsed.clues_found) ? parsed.clues_found : [];
    for (const item of cluesRaw) {
        if (clueIds.length >= MAX_CLUES_PER_TURN) {
            log(`Scene analyzer: dropped extra clue past per-turn cap (${MAX_CLUES_PER_TURN}).`, 'warn');
            break;
        }
        const id = String(item?.id ?? '').trim();
        const evidence = String(item?.evidence ?? '').trim();
        if (!id) continue;
        if (!availableIds.has(id)) {
            log(`Scene analyzer: dropped clue "${id}" — not in Available clues.`, 'warn');
            continue;
        }
        if (clueIds.includes(id)) continue;
        if (!evidence) {
            log(`Scene analyzer: dropped clue "${id}" — no evidence quoted.`, 'warn');
            continue;
        }
        if (!evidenceMatches(evidence, prose)) {
            log(`Scene analyzer: dropped clue "${id}" — evidence "${truncate(evidence, 80)}" not found in narration.`, 'warn');
            continue;
        }
        clueIds.push(id);
    }

    // --- node visited ---
    let nodeVisitedId = null;
    const visitedRaw = parsed.node_visited;
    if (visitedRaw && typeof visitedRaw === 'string') {
        const id = visitedRaw.trim();
        if (reachableIds.has(id)) {
            nodeVisitedId = id;
        } else if (id) {
            log(`Scene analyzer: dropped node_visited "${id}" — not in Reachable nodes.`, 'warn');
        }
    }

    // --- node completed ---
    let nodeCompletedId = null;
    const completedRaw = parsed.node_completed;
    if (completedRaw && typeof completedRaw === 'string') {
        const id = completedRaw.trim();
        const currentId = currentNode?.id ?? null;
        if (reachableIds.has(id) || id === currentId) {
            nodeCompletedId = id;
        } else if (id) {
            log(`Scene analyzer: dropped node_completed "${id}" — not in Reachable nodes or current node.`, 'warn');
        }
    }

    const notes = String(parsed.notes ?? '').trim();
    return { clueIds, nodeVisitedId, nodeCompletedId, notes, raw, ranLLM: true };
}

/**
 * Run the analyzer and apply its decisions to story state. Synthesizes the same
 * tag shapes the existing dispatcher consumes, so all downstream side-effects
 * (writeStoryState, AN re-render, undo bookkeeping) keep working unchanged.
 *
 * Returns the analyzer result so callers can log/surface what happened.
 */
export async function runAnalyzerAndApply({ messageText, userTurnText = '' }) {
    const settings = getSettings();
    if (settings.analyzer?.enabled === false) {
        log('Scene analyzer skipped — disabled in settings.', 'info');
        return { clueIds: [], nodeVisitedId: null, nodeCompletedId: null, notes: '', raw: '', ranLLM: false, applied: false };
    }

    const result = await analyzeAssistantMessage({ messageText, userTurnText });
    if (!result.ranLLM) {
        return { ...result, applied: false };
    }

    const synthetic = [];
    for (const clueId of result.clueIds) {
        synthetic.push({ kind: 'clue', key: 'found', value: clueId, raw: '' });
    }
    if (result.nodeVisitedId) {
        synthetic.push({ kind: 'node', key: result.nodeVisitedId, value: 'visited', raw: '' });
    }
    if (result.nodeCompletedId) {
        synthetic.push({ kind: 'node', key: result.nodeCompletedId, value: 'complete', raw: '' });
    }

    if (synthetic.length === 0) {
        log(`Scene analyzer: no state changes${result.notes ? ` (${result.notes})` : ''}.`, 'info');
        return { ...result, applied: false };
    }

    // Late import to break the analyzer ↔ closure_tags cycle.
    const { applyTagsToState } = await import('./closure_tags.js');
    await applyTagsToState(synthetic, { fromAnalyzer: true });

    const summary = [
        result.clueIds.length ? `clues=[${result.clueIds.join(', ')}]` : null,
        result.nodeVisitedId ? `visited=${result.nodeVisitedId}` : null,
        result.nodeCompletedId ? `completed=${result.nodeCompletedId}` : null,
    ].filter(Boolean).join(' · ');
    log(`Scene analyzer applied: ${summary}${result.notes ? ` — ${result.notes}` : ''}.`, 'info');

    return { ...result, applied: true };
}
