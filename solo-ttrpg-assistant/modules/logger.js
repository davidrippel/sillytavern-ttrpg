import { MAX_LOG_ENTRIES } from './constants.js';
import { getSettings, saveSettings } from './util.js';

const subscribers = new Set();

export function subscribeLog(listener) {
    subscribers.add(listener);
    return () => subscribers.delete(listener);
}

function emit() {
    for (const listener of subscribers) {
        listener();
    }
}

export function log(message, level = 'info', details = null) {
    const settings = getSettings();
    settings.logs.unshift({
        timestamp: new Date().toISOString(),
        level,
        message,
        details,
    });
    settings.logs = settings.logs.slice(0, MAX_LOG_ENTRIES);
    saveSettings();
    emit();
}

export function getLogs() {
    return getSettings().logs ?? [];
}
