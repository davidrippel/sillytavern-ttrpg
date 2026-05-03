import { mountSettingsPanel } from './settings.js';
import { initDiceModule } from './modules/dice.js';
import { maybeHandleStatusUpdate } from './modules/status_update.js';
import { runCompatibilityCheck } from './modules/pack.js';
import { formatCharacterSheetForPrompt } from './modules/sheet.js';
import { handleAssistantMessage as handleClosureTags } from './modules/closure_tags.js';
import {
    ensureStoryStateInitialized,
    refreshSummariesSilently,
    renderAuthorsNoteFromState,
} from './modules/authors_note.js';
import { writeStoryState, readStoryState } from './modules/util.js';
import { STORY_STATE_KEY } from './modules/constants.js';
import {
    findCharacterForPersona,
    getActiveCharacter,
    handleExternalPersonaChange,
    isPersonaSyncSuppressed,
} from './modules/characters.js';
import { log } from './modules/logger.js';
import {
    getCurrentPersonaKey,
    isExtensionEnabled,
    getNoteDepth,
    getNotePosition,
    getPersonasMap,
    getSettings,
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

// Debug helpers exposed on globalThis for browser-console use.
globalThis.soloTtrpgResetStoryState = async function soloTtrpgResetStoryState() {
    const ctx = globalThis.SillyTavern.getContext();
    if (ctx.chatMetadata) {
        delete ctx.chatMetadata[STORY_STATE_KEY];
        await ctx.saveMetadata();
    }
    log(`Story state cleared from chatMetadata. Next GM tag will re-seed it.`, 'info');
    await ensureStoryStateInitialized();
    await renderAuthorsNoteFromState({ preserveSummaries: false });
    log(`Story state re-initialized and AN re-rendered.`, 'info');
};

globalThis.soloTtrpgDumpStoryState = function soloTtrpgDumpStoryState() {
    const state = readStoryState();
    log(`Story state dump: ${JSON.stringify(state)}`, 'info');
    return state;
};

async function initUi() {
    if (initialized) {
        return;
    }
    initialized = true;
    await mountSettingsPanel();
    initDiceModule();
    await runCompatibilityCheck();
    log('Solo TTRPG Assistant initialized.');
}

context.eventSource.on(context.eventTypes.APP_READY, initUi);
let assistantMessageCount = 0;

context.eventSource.on(context.eventTypes.CHAT_CHANGED, async () => {
    assistantMessageCount = 0;
    if (!isExtensionEnabled()) {
        return;
    }
    await runCompatibilityCheck();
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

context.eventSource.on(context.eventTypes.MESSAGE_RECEIVED, async (arg) => {
    if (!isExtensionEnabled()) return;
    const settings = getSettings();
    const message = resolveChatMessage(arg);
    if (!message) return;

    if (settings.statusUpdate?.enabled !== false) {
        await maybeHandleStatusUpdate(message);
    }

    if (!message.is_user) {
        try {
            await ensureStoryStateInitialized();
        } catch (error) {
            log(`ensureStoryStateInitialized threw: ${error.message}`, 'warn');
        }

        await handleClosureTags(message);

        assistantMessageCount += 1;
        const cadence = Math.max(1, Number(settings.authorsNote?.autoSummaryEvery ?? 3));
        if (assistantMessageCount % cadence === 0) {
            refreshSummariesSilently().catch(() => {});
        }
    }
});

let lastSeenUserAvatar = null;

async function handlePersonaAvatarChange() {
    if (!isExtensionEnabled()) {
        return;
    }

    const nextKey = await getCurrentPersonaKey();
    if (!nextKey || nextKey === lastSeenUserAvatar) {
        return;
    }
    lastSeenUserAvatar = nextKey;

    if (isPersonaSyncSuppressed()) {
        return;
    }

    const match = findCharacterForPersona(nextKey);
    if (match) {
        await handleExternalPersonaChange(nextKey);
        return;
    }

    // Unlinked persona: offer to link the current character or create a new one.
    const active = getActiveCharacter();
    const personaName = getPersonasMap()[nextKey] ?? nextKey;
    toastr.info(
        `Switched to persona "${personaName}", which isn't linked to any TTRPG character.` +
        (active ? ` Open the character sheet to link "${active.name || 'the current character'}" or create a new one.` : ''),
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
