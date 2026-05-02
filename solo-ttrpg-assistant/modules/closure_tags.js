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
import { renderAuthorsNoteFromState, ensureStoryStateInitialized } from './authors_note.js';

const TAG_REGEX = /<<(beat|act|clue):([^:>\s]+):([^:>\s]+)>>/g;

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
    for (let i = Math.max(0, currentIdx); i <= resolvedIdx; i++) {
        const lbl = beatLabels[i];
        if (lbl && !next.resolvedBeatLabels.includes(lbl)) {
            next.resolvedBeatLabels.push(lbl);
        }
    }

    const advancedAct = isLastBeatOfAct(act, label);
    if (advancedAct) {
        return { state: next, changed: true, advancedAct: true };
    }

    next.currentBeatLabel = beatLabels[resolvedIdx + 1] ?? null;
    next.nextBeatLabel = next.currentBeatLabel ? nextBeatLabel(act, next.currentBeatLabel) : null;
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
    const next = { ...state, discoveredClues: [...state.discoveredClues, clueId] };
    log(`Discovered clue: ${clueId}.`);
    return { state: next, changed: true };
}

export async function applyTagsToState(tags) {
    let state = ensureStoryStateShape(readStoryState());
    if (!state.currentBeatLabel) {
        const initialized = await ensureStoryStateInitialized();
        if (initialized) state = ensureStoryStateShape(initialized);
    }

    let { acts } = await loadAllActs();
    let currentAct = acts.find((a) => a.actNumber === state.actNumber) ?? null;
    let anyChanged = false;

    for (const tag of tags) {
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
        await renderAuthorsNoteFromState({ preserveSummaries: true });
    }
    return { state, changed: anyChanged };
}

export async function moveBeatForwardManually() {
    const state = ensureStoryStateShape(readStoryState());
    if (!state.currentBeatLabel) {
        await ensureStoryStateInitialized();
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

    try {
        await applyTagsToState(tags);
    } catch (error) {
        log('Closure-tag handler failed.', 'warn', error.message);
    }
}
