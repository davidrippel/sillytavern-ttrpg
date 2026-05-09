import { log } from './logger.js';
import {
    readStoryState,
    writeStoryState,
    ensureStoryStateShape,
} from './util.js';
import {
    loadAllActs,
    nextBeatLabel,
    isLastBeatOfAct,
    rewriteCurrentActLorebookEntry,
} from './plot_skeleton.js';
import { loadAllClues, clueExists } from './clue_chains.js';
import { loadAllNodes, nodeExists, isCampaignNodeMode } from './nodes.js';
import { renderAuthorsNoteFromState, ensureStoryStateInitialized } from './authors_note.js';

// Value group permits `=` and `,` so <<npc:ID:state:KEY=VALUE,KEY=VALUE>> parses.
// `>` and whitespace remain disallowed so tag boundaries stay unambiguous.
const TAG_REGEX = /<<(beat|act|clue|node|npc):([^:>\s]+):([^>\s]+)>>/g;

const VISITED_NODES_CAP = 32;

export function parseClosureTags(text) {
    const tags = [];
    const matches = String(text ?? '').matchAll(TAG_REGEX);
    for (const m of matches) {
        tags.push({ kind: m[1], key: m[2], value: m[3], raw: m[0] });
    }
    return tags;
}

export function stripClosureTags(text, tags) {
    let out = String(text ?? '');
    for (const tag of tags) {
        out = out.split(tag.raw).join('');
    }
    return out.replace(/\n{3,}/g, '\n\n').replace(/[ \t]+\n/g, '\n').trim();
}

async function applyBeatResolved(label, state, act) {
    if (!act) {
        log(`beat:${label}:resolved ignored — no current act loaded.`, 'warn');
        return { state, changed: false, advancedAct: false };
    }
    const beatExists = act.beats.some((b) => b.label === label);
    if (!beatExists) {
        log(`beat:${label}:resolved ignored — label not found in Act ${act.actNumber}.`, 'warn');
        return { state, changed: false, advancedAct: false };
    }
    if (state.resolvedBeatLabels.includes(label)) {
        return { state, changed: false, advancedAct: false };
    }

    const beatLabels = act.beats.map((b) => b.label);
    const resolvedIdx = beatLabels.indexOf(label);
    const currentIdx = state.currentBeatLabel ? beatLabels.indexOf(state.currentBeatLabel) : 0;

    const next = { ...state };
    next.resolvedBeatLabels = [...state.resolvedBeatLabels];
    next.pendingReveals = [...(state.pendingReveals ?? [])];
    const queuedThisAdvance = [];

    // Queue any beats between the current and resolved (exclusive of resolved) as
    // pending reveals — content that the fiction skipped past but still owes the player.
    // The resolved beat itself is recorded normally.
    for (let i = Math.max(0, currentIdx); i < resolvedIdx; i++) {
        const lbl = beatLabels[i];
        if (!lbl) continue;
        if (next.resolvedBeatLabels.includes(lbl)) continue;
        if (next.pendingReveals.some((r) => r.label === lbl)) continue;
        const beat = act.beats.find((b) => b.label === lbl);
        next.pendingReveals.push({
            label: lbl,
            text: beat?.text ?? lbl,
            skippedAt: Date.now(),
        });
        queuedThisAdvance.push(lbl);
        log(`Beat ${lbl} skipped — queued as pending reveal.`, 'warn');
    }
    next._lastAdvanceQueuedLabels = queuedThisAdvance;
    next._lastAdvanceDrainedReveal = null;
    if (!next.resolvedBeatLabels.includes(label)) {
        next.resolvedBeatLabels.push(label);
    }

    const advancedAct = isLastBeatOfAct(act, label);
    if (advancedAct) {
        return { state: next, changed: true, advancedAct: true };
    }

    next.currentBeatLabel = beatLabels[resolvedIdx + 1] ?? null;
    next.nextBeatLabel = next.currentBeatLabel ? nextBeatLabel(act, next.currentBeatLabel) : null;
    if ((next.pendingReveals?.length ?? 0) > 0) {
        log(`Beat advanced with ${next.pendingReveals.length} pending reveal(s) still queued.`, 'info');
    }
    return { state: next, changed: true, advancedAct: false };
}

async function advanceToNextAct(state) {
    const targetActNumber = state.actNumber + 1;
    const { acts } = await loadAllActs();
    const target = acts.find((a) => a.actNumber === targetActNumber);
    if (!target) {
        log(`No Act ${targetActNumber} found in lorebook — campaign appears complete.`);
        const next = { ...state, completedActs: [...state.completedActs, state.actNumber] };
        return next;
    }

    await rewriteCurrentActLorebookEntry(targetActNumber);

    const next = {
        ...state,
        completedActs: [...state.completedActs, state.actNumber],
        actNumber: targetActNumber,
        currentBeatLabel: target.beats[0]?.label ?? null,
        nextBeatLabel: target.beats[1]?.label ?? null,
    };
    log(`Advanced to Act ${targetActNumber}: ${target.title}.`);
    return next;
}

async function applyActComplete(actNumber, state) {
    if (state.actNumber !== actNumber) {
        log(`act:${actNumber}:complete ignored — current actNumber is ${state.actNumber}.`, 'warn');
        return { state, changed: false };
    }
    const advanced = await advanceToNextAct(state);
    return { state: advanced, changed: true };
}

async function applyClueFound(clueId, state) {
    if (state.discoveredClues.includes(clueId)) {
        return { state, changed: false };
    }
    const clues = await loadAllClues();
    if (!clueExists(clues, clueId)) {
        log(`clue:found:${clueId} ignored — id not found in clue lorebook entries.`, 'warn');
        return { state, changed: false };
    }
    const next = {
        ...state,
        discoveredClues: [...state.discoveredClues, clueId],
        _lastStateChange: { kind: 'clue_found', clueId },
    };
    log(`Discovered clue: ${clueId}.`);
    return { state: next, changed: true };
}

async function applyNodeVisited(nodeId, state) {
    const visited = state.visitedNodes ?? [];
    if (visited.includes(nodeId)) {
        return { state, changed: false };
    }
    const nodes = await loadAllNodes();
    if (!nodeExists(nodes, nodeId)) {
        log(`node:${nodeId}:visited ignored — id not found in node lorebook entries.`, 'warn');
        return { state, changed: false };
    }
    const trimmed = visited.length >= VISITED_NODES_CAP
        ? visited.slice(visited.length - VISITED_NODES_CAP + 1)
        : visited;
    const next = {
        ...state,
        visitedNodes: [...trimmed, nodeId],
        _lastStateChange: { kind: 'node_visited', nodeId },
    };
    log(`Visited node: ${nodeId}.`);
    return { state: next, changed: true };
}

async function applyNodeComplete(nodeId, state) {
    const completed = state.completedNodes ?? [];
    if (completed.includes(nodeId)) {
        return { state, changed: false };
    }
    const nodes = await loadAllNodes();
    if (!nodeExists(nodes, nodeId)) {
        log(`node:${nodeId}:complete ignored — id not found in node lorebook entries.`, 'warn');
        return { state, changed: false };
    }
    const next = {
        ...state,
        completedNodes: [...completed, nodeId],
        _lastStateChange: { kind: 'node_complete', nodeId },
    };
    log(`Completed node: ${nodeId}.`);
    return { state: next, changed: true };
}

function parseNpcStateKv(kvString) {
    const out = {};
    for (const part of String(kvString ?? '').split(',')) {
        const eq = part.indexOf('=');
        if (eq < 0) continue;
        const key = part.slice(0, eq).trim();
        const value = part.slice(eq + 1).trim();
        if (!key) continue;
        out[key] = value;
    }
    return out;
}

function applyNpcState(npcId, kvString, state, turnCount) {
    const updates = parseNpcStateKv(kvString);
    if (Object.keys(updates).length === 0) {
        log(`npc:${npcId}:state ignored — no parseable KEY=VALUE pairs in "${kvString}".`, 'warn');
        return { state, changed: false };
    }
    const prior = state.npcs?.[npcId] ?? {};
    const merged = { ...prior, ...updates, last_seen_turn: turnCount };
    const next = {
        ...state,
        npcs: { ...(state.npcs ?? {}), [npcId]: merged },
        _lastStateChange: { kind: 'npc_state', npcId, prior },
    };
    log(`NPC ${npcId} state updated: ${Object.keys(updates).join(', ')}.`);
    return { state: next, changed: true };
}

export async function applyTagsToState(tags, { turnCount = 0 } = {}) {
    const nodeMode = await isCampaignNodeMode();

    let state = ensureStoryStateShape(readStoryState());
    if (!nodeMode && !state.currentBeatLabel) {
        const initialized = await ensureStoryStateInitialized();
        if (initialized) state = ensureStoryStateShape(initialized);
    }

    let acts = [];
    let currentAct = null;
    if (!nodeMode) {
        ({ acts } = await loadAllActs());
        currentAct = acts.find((a) => a.actNumber === state.actNumber) ?? null;
    }
    let anyChanged = false;

    for (const tag of tags) {
        if (nodeMode) {
            if (tag.kind === 'beat' || tag.kind === 'act') {
                log(`${tag.kind} tag ${tag.raw} ignored — campaign is in node-mode.`, 'info');
                continue;
            }
            if (tag.kind === 'node' && tag.value === 'visited') {
                const result = await applyNodeVisited(tag.key, state);
                if (result.changed) { state = result.state; anyChanged = true; }
            } else if (tag.kind === 'node' && tag.value === 'complete') {
                const result = await applyNodeComplete(tag.key, state);
                if (result.changed) { state = result.state; anyChanged = true; }
            } else if (tag.kind === 'npc') {
                // Shape: <<npc:ID:state:KEY=VALUE,...>>. The regex captures
                // group2=ID and group3="state:KEY=VALUE,...".
                const value = String(tag.value ?? '');
                if (value.startsWith('state:')) {
                    const kv = value.slice('state:'.length);
                    const result = applyNpcState(tag.key, kv, state, turnCount);
                    if (result.changed) { state = result.state; anyChanged = true; }
                } else {
                    log(`npc tag ${tag.raw} ignored — unrecognized form.`, 'warn');
                }
            } else if (tag.kind === 'clue' && tag.key === 'found') {
                const result = await applyClueFound(tag.value, state);
                if (result.changed) { state = result.state; anyChanged = true; }
            }
            continue;
        }

        // Beat-mode (legacy) dispatch
        if (tag.kind === 'node' || tag.kind === 'npc') {
            log(`${tag.kind} tag ${tag.raw} ignored — campaign is in beat-mode.`, 'info');
            continue;
        }
        if (tag.kind === 'beat' && tag.value === 'resolved') {
            const result = await applyBeatResolved(tag.key, state, currentAct);
            if (result.changed) {
                state = result.state;
                anyChanged = true;
                if (result.advancedAct) {
                    state = await advanceToNextAct(state);
                    ({ acts } = await loadAllActs());
                    currentAct = acts.find((a) => a.actNumber === state.actNumber) ?? null;
                }
            }
        } else if (tag.kind === 'act' && tag.value === 'complete') {
            const n = Number(tag.key);
            if (Number.isFinite(n)) {
                const result = await applyActComplete(n, state);
                if (result.changed) {
                    state = result.state;
                    anyChanged = true;
                    ({ acts } = await loadAllActs());
                    currentAct = acts.find((a) => a.actNumber === state.actNumber) ?? null;
                }
            }
        } else if (tag.kind === 'clue' && tag.key === 'found') {
            const result = await applyClueFound(tag.value, state);
            if (result.changed) {
                state = result.state;
                anyChanged = true;
            }
        }
    }

    if (anyChanged) {
        await writeStoryState(state);
        try {
            await renderAuthorsNoteFromState({ preserveSummaries: true });
        } catch (error) {
            log(`renderAuthorsNoteFromState threw: ${error.message}`, 'warn');
        }
    }
    return { state, changed: anyChanged };
}

export function canRevertLastAdvance() {
    const state = ensureStoryStateShape(readStoryState());
    return (state.resolvedBeatLabels?.length ?? 0) > 0
        || (state.completedActs?.length ?? 0) > 0
        || !!state._lastAdvanceDrainedReveal
        || !!state._lastStateChange;
}

export async function revertLastStateChange() {
    const state = ensureStoryStateShape(readStoryState());
    const change = state._lastStateChange;
    if (!change) {
        log('Undo ignored — no recent state change recorded.', 'info');
        return false;
    }

    const next = { ...state, _lastStateChange: null };
    if (change.kind === 'node_visited') {
        next.visitedNodes = (state.visitedNodes ?? []).filter((id) => id !== change.nodeId);
    } else if (change.kind === 'node_complete') {
        next.completedNodes = (state.completedNodes ?? []).filter((id) => id !== change.nodeId);
    } else if (change.kind === 'clue_found') {
        next.discoveredClues = (state.discoveredClues ?? []).filter((id) => id !== change.clueId);
    } else if (change.kind === 'npc_state') {
        const npcs = { ...(state.npcs ?? {}) };
        if (change.prior && Object.keys(change.prior).length > 0) {
            npcs[change.npcId] = change.prior;
        } else {
            delete npcs[change.npcId];
        }
        next.npcs = npcs;
    } else {
        log(`Undo ignored — unknown change kind ${change.kind}.`, 'warn');
        return false;
    }

    await writeStoryState(next);
    try {
        await renderAuthorsNoteFromState({ preserveSummaries: true });
    } catch (error) {
        log(`renderAuthorsNoteFromState threw: ${error.message}`, 'warn');
    }
    log(`Reverted ${change.kind}.`, 'info');
    return true;
}

export async function revertLastBeatAdvance() {
    const state = ensureStoryStateShape(readStoryState());
    if ((state.resolvedBeatLabels?.length ?? 0) === 0
        && (state.completedActs?.length ?? 0) === 0
        && !state._lastAdvanceDrainedReveal) {
        log('Move plot back ignored — no advances to revert.', 'info');
        return false;
    }

    // Case 0: last action was draining a pending reveal — push it back to the front.
    if (state._lastAdvanceDrainedReveal) {
        const next = {
            ...state,
            pendingReveals: [state._lastAdvanceDrainedReveal, ...(state.pendingReveals ?? [])],
            _lastAdvanceDrainedReveal: null,
            _lastAdvanceQueuedLabels: [],
        };
        await writeStoryState(next);
        await renderAuthorsNoteFromState({ preserveSummaries: true });
        log(`Reverted pending-reveal drain: ${state._lastAdvanceDrainedReveal.label} restored to queue.`, 'info');
        return true;
    }

    // Case A: most recent advance was an act-advance (currentBeatLabel is the
    // first beat of the current act, AND there is a completed act to roll back to).
    const { acts } = await loadAllActs();
    const currentAct = acts.find((a) => a.actNumber === state.actNumber);
    const isAtFirstBeat = currentAct && currentAct.beats[0]?.label === state.currentBeatLabel;
    const hasCompletedAct = (state.completedActs?.length ?? 0) > 0;

    if (isAtFirstBeat && hasCompletedAct) {
        const prevActNumber = state.completedActs[state.completedActs.length - 1];
        const prevAct = acts.find((a) => a.actNumber === prevActNumber);
        if (!prevAct) {
            log(`Move plot back: prior Act ${prevActNumber} not found in lorebook.`, 'warn');
            return false;
        }

        await rewriteCurrentActLorebookEntry(prevActNumber);

        const lastResolvedOfPrev = prevAct.beats[prevAct.beats.length - 1]?.label ?? null;
        const next = {
            ...state,
            actNumber: prevActNumber,
            completedActs: state.completedActs.slice(0, -1),
            // Restore prior act's last beat as Current; keep its resolvedBeatLabels
            // as-is — the player decides whether to undo within-act steps after.
            currentBeatLabel: lastResolvedOfPrev,
            nextBeatLabel: null,
        };
        // Pop the last-beat resolution of the prior act so the within-act undo
        // is consistent (prior act's last beat is now "current", not resolved).
        if (lastResolvedOfPrev && next.resolvedBeatLabels.includes(lastResolvedOfPrev)) {
            next.resolvedBeatLabels = next.resolvedBeatLabels.filter((l) => l !== lastResolvedOfPrev);
        }
        await writeStoryState(next);
        await renderAuthorsNoteFromState({ preserveSummaries: true });
        log(`Reverted act advance: now at Act ${prevActNumber}, beat ${lastResolvedOfPrev}.`, 'info');
        return true;
    }

    // Case B: undo within-act beat advance.
    if (!currentAct) {
        log('Move plot back ignored — current act not loadable.', 'warn');
        return false;
    }
    if ((state.resolvedBeatLabels?.length ?? 0) === 0) {
        log('Move plot back ignored — no resolved beats in current act.', 'info');
        return false;
    }

    const beatLabels = currentAct.beats.map((b) => b.label);
    const lastResolved = state.resolvedBeatLabels[state.resolvedBeatLabels.length - 1];
    const lastResolvedIdx = beatLabels.indexOf(lastResolved);
    if (lastResolvedIdx < 0) {
        log(`Move plot back ignored — last resolved beat ${lastResolved} not found in current act.`, 'warn');
        return false;
    }

    // Drop any pending reveals that were queued during the advance we're undoing.
    const queuedLabels = new Set(state._lastAdvanceQueuedLabels ?? []);
    const restoredPending = queuedLabels.size > 0
        ? (state.pendingReveals ?? []).filter((r) => !queuedLabels.has(r.label))
        : (state.pendingReveals ?? []);

    const next = {
        ...state,
        resolvedBeatLabels: state.resolvedBeatLabels.slice(0, -1),
        currentBeatLabel: lastResolved,
        nextBeatLabel: beatLabels[lastResolvedIdx + 1] ?? null,
        pendingReveals: restoredPending,
        _lastAdvanceQueuedLabels: [],
        _lastAdvanceDrainedReveal: null,
    };
    await writeStoryState(next);
    await renderAuthorsNoteFromState({ preserveSummaries: true });
    log(`Reverted beat advance: now at beat ${lastResolved}.`, 'info');
    return true;
}

export async function resetCampaignState() {
    const ctx = (await import('./util.js')).getContext();
    if (ctx.chatMetadata) {
        delete ctx.chatMetadata.solo_ttrpg_story_state;
        await ctx.saveMetadata();
    }
    log('Story state cleared. Re-seeding from lorebook…', 'info');
    const initialized = await ensureStoryStateInitialized();
    if (!initialized) {
        log('resetCampaignState: could not re-seed — lorebook may not be bound yet.', 'warn');
        return false;
    }
    await renderAuthorsNoteFromState({ preserveSummaries: false });
    log('Campaign reset complete. Author\'s Note re-rendered.', 'info');
    return true;
}

export async function moveBeatForwardManually() {
    if (await isCampaignNodeMode()) {
        log('Move plot forward is a no-op in node-mode — use the node picker UI to mark a node visited.', 'info');
        return;
    }
    const state = ensureStoryStateShape(readStoryState());
    if (!state.currentBeatLabel) {
        await ensureStoryStateInitialized();
        return;
    }
    if ((state.pendingReveals?.length ?? 0) > 0) {
        const [drained, ...rest] = state.pendingReveals;
        const next = {
            ...state,
            pendingReveals: rest,
            _lastAdvanceQueuedLabels: [],
            _lastAdvanceDrainedReveal: drained,
        };
        await writeStoryState(next);
        try {
            await renderAuthorsNoteFromState({ preserveSummaries: true });
        } catch (error) {
            log(`renderAuthorsNoteFromState threw: ${error.message}`, 'warn');
        }
        log(`Drained pending reveal: ${drained.label}.`, 'info');
        return;
    }
    await applyTagsToState([{ kind: 'beat', key: state.currentBeatLabel, value: 'resolved', raw: '' }]);
}

export async function handleAssistantMessage(message) {
    if (!message || message.is_user) return;
    const text = String(message.mes ?? '');
    if (!text.includes('<<')) return;

    const tags = parseClosureTags(text);
    if (tags.length === 0) return;

    const stripped = stripClosureTags(text, tags);
    if (stripped !== text) {
        message.mes = stripped;
    }

    let turnCount = 0;
    try {
        const ctx = (await import('./util.js')).getContext();
        turnCount = Array.isArray(ctx?.chat) ? ctx.chat.length : 0;
    } catch { /* turnCount stays 0 — only used for npc:state, which still works */ }

    try {
        const result = await applyTagsToState(tags, { turnCount });
        if (result.changed) {
            const s = result.state;
            const summary = (s.visitedNodes?.length || s.completedNodes?.length || Object.keys(s.npcs ?? {}).length)
                ? `nodes=${s.visitedNodes?.length ?? 0}/${s.completedNodes?.length ?? 0}, npcs=${Object.keys(s.npcs ?? {}).length}, clues=${s.discoveredClues?.length ?? 0}`
                : `currentBeat=${s.currentBeatLabel}, nextBeat=${s.nextBeatLabel}`;
            log(`Closure tags applied: ${summary}`, 'info');
        }
    } catch (error) {
        log('Closure-tag handler failed.', 'warn', error.message);
    }
}
