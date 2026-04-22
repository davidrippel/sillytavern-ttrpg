import { mountSettingsPanel } from './settings.js';
import { initDiceModule } from './modules/dice.js';
import { maybeHandleStatusUpdate } from './modules/status_update.js';
import { runCompatibilityCheck } from './modules/pack.js';
import { formatCharacterSheetForPrompt } from './modules/sheet.js';
import { log } from './modules/logger.js';
import { getNoteDepth, getNotePosition, getSettings } from './modules/util.js';

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
    if (!settings.sheetInjection?.enabled) {
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
    await runCompatibilityCheck();
});
context.eventSource.on(context.eventTypes.MESSAGE_RECEIVED, async (message) => {
    const settings = getSettings();
    if (settings.statusUpdate?.enabled !== false) {
        await maybeHandleStatusUpdate(message);
    }
});
