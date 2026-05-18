// index.js — extension entry point (v3, story-mode-only runtime).
//
// Per-turn flow for an assistant message:
//
//   1. Auto-commit any provisional facts older than the cooldown.
//   2. Increment turn counter.
//   3. Run the fact extractor against the new assistant prose.
//   4. Apply the extractor's diff:
//        - append provisional facts (ready for the inline chip strip)
//        - open new threads / advance existing ones
//        - update scene context + on-screen NPCs
//        - record any truths the prose touched
//   5. Run the pacing module: compute a pressure cue, optionally
//      select a director's note from the campaign truths.
//   6. Reevaluate tier-2 secret lorebook unlocks.
//   7. Rebuild the Author's Note from state.
//   8. Render inline fact chips on the new message, refresh the
//      threads tray.
//
// Closure tags (<<beat:..>>, <<clue:..>>, <<node:..>>, <<npc:..>>)
// are retired. If a GM somehow emits one we just leave it in the
// message — there's no parser to strip it. The base prompt explicitly
// forbids the syntax.

import { mountSettingsPanel } from './settings.js';
import { runCompatibilityCheck } from './modules/pack.js';
import { formatCharacterSheetForPrompt } from './modules/sheet.js';
import {
    ensureStoryStateInitialized,
    renderAuthorsNoteFromState,
} from './modules/authors_note.js';
import {
    findCharacterForPersona,
    getActiveCharacter,
    handleExternalPersonaChange,
    isPersonaSyncSuppressed,
} from './modules/characters.js';
import { extractFromAssistantMessage } from './modules/facts_extractor.js';
import {
    appendProvisionalFacts,
    autoCommitStaleProvisional,
    FACT_STATUS,
} from './modules/facts.js';
import { advanceThread, listLiveThreads, openThread } from './modules/threads.js';
import { computePressureCue, selectDirectorsNote } from './modules/pacing.js';
import { loadCampaignTruths } from './modules/lorebook_v2.js';
import { reevaluateSecretUnlocks } from './modules/secrets.js';
import { refreshAllFactChips, renderFactChipsForLatestMessage, renderThreadsTray } from './modules/inline_ui.js';
import { log } from './modules/logger.js';
import {
    ensureStoryStateShape,
    getCurrentPersonaKey,
    getNoteDepth,
    getNotePosition,
    getPersonasMap,
    getSettings,
    isExtensionEnabled,
    readStoryState,
    writeStoryState,
} from './modules/util.js';

const context = globalThis.SillyTavern.getContext();
let initialized = false;

function buildInjectedSheetMessage() {
    return {
        name: 'Character Sheet',
        is_system: true,
        mes: formatCharacterSheetForPrompt(),
        extra: {
            type: 'system',
            isSmallSys: true,
        },
    };
}

function getInjectionIndex(chat) {
    const settings = getSettings();
    const fallbackDepth = Number(settings.sheetInjection?.fallbackDepth ?? 4);
    const notePosition = getNotePosition();
    const noteDepth = getNoteDepth();
    const targetDepth = notePosition === 1 ? noteDepth + 1 : fallbackDepth;
    return Math.max(0, chat.length - Math.max(1, targetDepth));
}

globalThis.soloTtrpgGenerateInterceptor = async function soloTtrpgGenerateInterceptor(chat) {
    const settings = getSettings();
    if (!isExtensionEnabled() || !settings.sheetInjection?.enabled) {
        return;
    }
    const message = buildInjectedSheetMessage();
    chat.splice(getInjectionIndex(chat), 0, message);
};

async function initUi() {
    if (initialized) return;
    initialized = true;
    await mountSettingsPanel();
    await runCompatibilityCheck();
    renderThreadsTray();
    log('Solo TTRPG Assistant v3 initialized.');
}

context.eventSource.on(context.eventTypes.APP_READY, initUi);

context.eventSource.on(context.eventTypes.CHAT_CHANGED, async () => {
    if (!isExtensionEnabled()) return;
    await runCompatibilityCheck();
    try {
        await ensureStoryStateInitialized();
    } catch {
        // Best-effort: a freshly bound chat may not have metadata yet.
    }
    refreshAllFactChips();
    renderThreadsTray();
});

function resolveChatMessage(arg) {
    if (arg && typeof arg === 'object' && 'mes' in arg) {
        return arg;
    }
    const chat = context.chat;
    if (!Array.isArray(chat)) return null;
    if (typeof arg === 'number' && arg >= 0 && arg < chat.length) {
        return chat[arg];
    }
    return chat[chat.length - 1] ?? null;
}

function previousUserMessage() {
    const chat = context.chat;
    if (!Array.isArray(chat)) return '';
    for (let i = chat.length - 1; i >= 0; i -= 1) {
        const msg = chat[i];
        if (msg?.is_user) return String(msg.mes ?? '');
    }
    return '';
}

context.eventSource.on(context.eventTypes.MESSAGE_RECEIVED, async (arg) => {
    if (!isExtensionEnabled()) return;
    const message = resolveChatMessage(arg);
    if (!message || message.is_user) return;

    try {
        await ensureStoryStateInitialized();
    } catch {
        return;
    }

    try {
        await runTurnPipeline(String(message.mes ?? ''));
    } catch (error) {
        log('Turn pipeline failed.', 'warn', error?.message ?? String(error));
    }
});

async function runTurnPipeline(assistantProse) {
    const settings = getSettings();
    const stateBefore = ensureStoryStateShape(readStoryState() ?? {});

    // 1. Auto-commit provisional facts older than the cooldown.
    const cooldown = Math.max(1, Number(settings.factExtractor?.autoCommitAfterTurns ?? 1));
    await autoCommitStaleProvisional(stateBefore.turn, cooldown);

    // 2. Bump turn.
    const state = ensureStoryStateShape(readStoryState() ?? {});
    state.turn = Number(state.turn || 0) + 1;
    await writeStoryState(state);

    // 3. Extractor.
    const recentFactsLines = state.facts
        .filter((f) => f.status === FACT_STATUS.accepted)
        .slice(-Number(settings.authorsNote?.recentFactsInAN ?? 8))
        .map((f) => `- ${truncate(f.text, 200)}`);
    const liveThreads = listLiveThreads(state);
    const liveThreadsLines = liveThreads.map(
        (t) => `- id: ${t.id} | question: ${truncate(t.question, 160)}`,
    );
    const sceneContextLine = [
        state.scene?.location ? `where: ${state.scene.location}` : null,
        state.scene?.tension ? `tension: ${state.scene.tension}` : null,
    ].filter(Boolean).join(' | ');
    const onScreenNpcsLine = (state.scene?.presentNpcIds ?? []).slice(0, 6).join(', ');

    const truths = await loadCampaignTruths();
    const truthsForExtractor = truths.slice(0, 12);

    const extracted = await extractFromAssistantMessage({
        assistantMessageText: assistantProse,
        userMessageText: previousUserMessage(),
        state,
        recentFactsLines,
        liveThreadsLines,
        sceneContextLine,
        onScreenNpcsLine,
        truthsForExtractor,
    });

    // 4. Apply the diff.
    if (extracted.newFacts.length > 0) {
        await appendProvisionalFacts(state.turn, extracted.newFacts);
    }

    for (const update of extracted.threadUpdates) {
        await advanceThread(update.threadId, { status: update.status, why: update.why, turn: state.turn });
    }
    for (const nt of extracted.newThreads) {
        await openThread({ question: nt.question, why: nt.why, turn: state.turn });
    }

    if (extracted.sceneDelta || extracted.npcState?.length || extracted.truthsTouched?.length) {
        const next = ensureStoryStateShape(readStoryState() ?? {});
        if (extracted.sceneDelta) {
            const delta = extracted.sceneDelta;
            if (delta.location) next.scene.location = delta.location;
            if (delta.tension) next.scene.tension = delta.tension;
            if (Array.isArray(delta.presentNpcIds)) next.scene.presentNpcIds = delta.presentNpcIds;
            next.scene.lastUpdatedTurn = next.turn;
        }
        if (extracted.npcState?.length) {
            for (const npc of extracted.npcState) {
                if (!npc.id) continue;
                const prev = next.npcs[npc.id] ?? {};
                next.npcs[npc.id] = {
                    ...prev,
                    lastSeenTurn: next.turn,
                    attitude: npc.attitude ?? prev.attitude ?? null,
                    status: npc.status ?? prev.status ?? null,
                };
            }
        }
        if (extracted.truthsTouched?.length) {
            // Record truth payouts when the active director's note is
            // among the touched truths — this is how the pacing module
            // knows the GM actually landed the reveal.
            const activeId = next.directorsNotes?.active?.truthId ?? null;
            for (const touch of extracted.truthsTouched) {
                if (touch.truthId === activeId
                    && !next.truthsRevealed.some((t) => t.truthId === activeId)) {
                    next.truthsRevealed.push({
                        truthId: activeId,
                        turn: next.turn,
                        how: touch.how ?? 'landed in fiction',
                    });
                    if (Array.isArray(next.directorsNotes.history)) {
                        next.directorsNotes.history.push({
                            ...next.directorsNotes.active,
                            paidOutTurn: next.turn,
                        });
                    }
                    next.directorsNotes.active = null;
                }
            }
        }
        await writeStoryState(next);
    }

    // 5. Pacing + director's note selection.
    {
        const cur = ensureStoryStateShape(readStoryState() ?? {});
        const cue = computePressureCue(cur);
        cur.pressureCue = { ...cur.pressureCue, ...cue, setTurn: cur.turn };
        const note = selectDirectorsNote({
            state: cur,
            pressureCue: cue,
            truths,
            liveThreads: listLiveThreads(cur),
            recentFacts: cur.facts.filter((f) => f.status === FACT_STATUS.accepted).slice(-8),
        });
        cur.directorsNotes.active = note;
        await writeStoryState(cur);
    }

    // 6. Secret unlocks (tier-2 lorebook entries).
    try {
        await reevaluateSecretUnlocks(ensureStoryStateShape(readStoryState() ?? {}));
    } catch (error) {
        log('Secret unlock pass failed.', 'warn', error?.message ?? String(error));
    }

    // 7. AN rebuild.
    try {
        await renderAuthorsNoteFromState();
    } catch (error) {
        log('AN render failed.', 'warn', error?.message ?? String(error));
    }

    // 8. Inline UI refresh.
    renderFactChipsForLatestMessage();
    renderThreadsTray();
}

function truncate(text, max) {
    const s = String(text ?? '').trim();
    if (s.length <= max) return s;
    return `${s.slice(0, max - 1)}…`;
}

// ---- Persona link (unchanged from v2) ----------------------------------

let lastSeenUserAvatar = null;

async function handlePersonaAvatarChange() {
    if (!isExtensionEnabled()) return;

    const nextKey = await getCurrentPersonaKey();
    if (!nextKey || nextKey === lastSeenUserAvatar) return;
    lastSeenUserAvatar = nextKey;

    if (isPersonaSyncSuppressed()) return;

    const match = findCharacterForPersona(nextKey);
    if (match) {
        await handleExternalPersonaChange(nextKey);
        return;
    }

    const active = getActiveCharacter();
    const personaName = getPersonasMap()[nextKey] ?? nextKey;
    toastr.info(
        `Switched to persona "${personaName}", which isn't linked to any TTRPG character.`
        + (active ? ` Open the character sheet to link "${active.name || 'the current character'}" or create a new one.` : ''),
        'Solo TTRPG Assistant',
        { timeOut: 6000 },
    );
}

function subscribePersonaEvents() {
    const types = context.eventTypes ?? {};
    const candidates = [
        types.SETTINGS_UPDATED,
        types.SETTINGS_LOADED,
        types.PERSONA_CHANGED,
        types.PERSONA_UPDATED,
    ].filter(Boolean);

    for (const eventType of candidates) {
        context.eventSource.on(eventType, () => {
            void handlePersonaAvatarChange();
        });
    }
}

subscribePersonaEvents();
