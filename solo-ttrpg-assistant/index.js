import { mountSettingsPanel } from './settings.js';
import { initDiceModule } from './modules/dice.js';
import { maybeHandleStatusUpdate } from './modules/status_update.js';
import { runCompatibilityCheck } from './modules/pack.js';
import { formatCharacterSheetForPrompt } from './modules/sheet.js';
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
context.eventSource.on(context.eventTypes.CHAT_CHANGED, async () => {
    if (!isExtensionEnabled()) {
        return;
    }
    await runCompatibilityCheck();
});
context.eventSource.on(context.eventTypes.MESSAGE_RECEIVED, async (message) => {
    const settings = getSettings();
    if (isExtensionEnabled() && settings.statusUpdate?.enabled !== false) {
        await maybeHandleStatusUpdate(message);
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
