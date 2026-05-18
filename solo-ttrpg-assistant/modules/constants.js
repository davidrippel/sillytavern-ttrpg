export const MODULE_NAME = 'solo_ttrpg_assistant';
export const DISPLAY_NAME = 'Solo TTRPG Assistant';
export const MAX_LOG_ENTRIES = 200;

// v2 (story-mode) pack files. The legacy stat-mode files (attributes.yaml,
// resources.yaml, abilities.yaml, failure_moves.md) are intentionally absent
// — they're rejected by the pack loader.
export const PACK_REQUIRED_FILES = [
    'pack.yaml',
    'character_template.json',
    'gm_prompt_overlay.md',
    'tone.md',
    'complications.md',
    'advantages_disadvantages.md',
    'example_hooks.md',
    'generator_seed.yaml',
];

export const AUTHORS_NOTE_KEYS = Object.freeze({
    prompt: 'note_prompt',
    interval: 'note_interval',
    depth: 'note_depth',
    position: 'note_position',
    role: 'note_role',
});

// v2 story-mode Author's Note sections.
// The runtime no longer tracks beats, nodes, clue chains, or acts.
// Every section here is keyed off the fact/thread/scene model in
// `solo_ttrpg_story_state` and either composed deterministically from state
// or, in a few cases, LLM-synthesised on a cadence.
export const AUTHORS_NOTE_SECTIONS = Object.freeze([
    'Thematic spine',
    'Live threads',
    'Recent facts',
    'Scene context',
    'On-screen NPCs',
    "Director's notes",
    'Pressure cue',
    'Tone reminders',
]);

export const STORY_STATE_KEY = 'solo_ttrpg_story_state';
// Bumped to v3 when the system moved from beats/nodes to facts/threads.
// State documents written under v1/v2 are auto-archived by the migration
// shim in util.js (see archiveLegacyStoryState).
export const STORY_STATE_SCHEMA_VERSION = 3;
export const STORY_STATE_ARCHIVE_KEY = 'solo_ttrpg_story_state_archive';

// Constant lorebook entries the campaign generator embeds for every campaign.
// The extension reads these to compose the AN and to derive director's notes.
export const PACK_LOREBOOK_ENTRIES = Object.freeze({
    overlay: '__pack_gm_overlay',
    complications: '__pack_complications',
    reference: '__pack_reference',
    bible: '__campaign_bible',
});

export const FACT_LIMITS = Object.freeze({
    recentFactsInAN: 8,
    maxFactsPerExtraction: 5,
    factsAutoCommitAfterTurns: 0,
});

export const THREAD_LIMITS = Object.freeze({
    liveThreadsInAN: 3,
    maxLiveThreads: 8,
});

export const PACING = Object.freeze({
    leanInAfterTurnsWithoutTruth: 6,
    leanInAfterTurnsThreadStalled: 5,
    cooldownTurnsAfterTruth: 2,
});

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
        recentFactsInAN: FACT_LIMITS.recentFactsInAN,
        autoSummaryEvery: 3,
    },
    factExtractor: {
        enabled: true,
        autoCommitAfterTurns: FACT_LIMITS.factsAutoCommitAfterTurns,
    },
    ui: {
        inlineFactChips: true,
        threadsTray: true,
    },
});

export function getExtensionPath() {
    return 'third-party/solo-ttrpg-assistant';
}
