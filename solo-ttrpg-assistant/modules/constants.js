export const MODULE_NAME = 'solo_ttrpg_assistant';
export const DISPLAY_NAME = 'Solo TTRPG Assistant';
export const QR_SET_NAME = 'Solo TTRPG Rolls';
export const MAX_LOG_ENTRIES = 200;

export const PACK_REQUIRED_FILES = [
    'pack.yaml',
    'attributes.yaml',
    'resources.yaml',
    'abilities.yaml',
    'character_template.json',
];

export const AUTHORS_NOTE_KEYS = Object.freeze({
    prompt: 'note_prompt',
    interval: 'note_interval',
    depth: 'note_depth',
    position: 'note_position',
    role: 'note_role',
});

export const AUTHORS_NOTE_SECTIONS = Object.freeze([
    'Current Act',
    'Current beat',
    'Next beat',
    'Discovered clues',
    'Available clues',
    'Active threads',
    'Recent beats',
    'Reminders',
]);

export const STORY_STATE_KEY = 'solo_ttrpg_story_state';
export const STORY_STATE_SCHEMA_VERSION = 1;

export const DEFAULT_SETTINGS = Object.freeze({
    enabled: true,
    packs: {},
    activePackName: null,
    activePack: null,
    characters: {},
    activeCharacterId: null,
    logs: [],
    sheetInjection: {
        enabled: true,
        fallbackDepth: 4,
    },
    backup: {
        autoExportMode: 'never',
    },
    authorsNote: {
        recentBeatsMessages: 8,
        autoSummaryEvery: 3,
    },
    statusUpdate: {
        enabled: true,
    },
    canonDetection: {
        enabled: false,
    },
});

export function getExtensionPath() {
    return 'third-party/solo-ttrpg-assistant';
}
