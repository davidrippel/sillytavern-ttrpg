// authors_note.js — v3 Author's Note composition.
//
// In v2 the AN was a hybrid: some sections came from state (Current
// beat, Reachable nodes) and some were LLM-synthesised every few turns
// (Active threads, Recent beats, Reminders). The v3 AN is fully
// derived from state — the fact extractor populates state, the AN
// renders it. There are no per-N-turn LLM summary calls anymore.
//
// Section vocabulary (see constants.js → AUTHORS_NOTE_SECTIONS):
//
//   Thematic spine       — short reminder pulled from the campaign
//                          bible (lorebook). Filled in only when we
//                          can find the spine; otherwise blank.
//   Live threads         — up to 3 active threads, most-recently
//                          advanced first.
//   Recent facts         — last N accepted facts, oldest-to-newest.
//   Scene context        — location + tension, derived from state.
//   On-screen NPCs       — NPCs the extractor marked present recently.
//   Director's notes     — at most one campaign truth that the pacing
//                          module has marked reveal-eligible.
//   Pressure cue         — "lean in" / "let it breathe" / "introduce
//                          a complication" hint.
//   Tone reminders       — short pointer to the pack overlay.
//
// AN composition is fast and deterministic. Callers can rebuild it
// after every state mutation without burning LLM tokens.

import { AUTHORS_NOTE_SECTIONS, FACT_LIMITS, PACK_LOREBOOK_ENTRIES, THREAD_LIMITS } from './constants.js';
import { listRecentAcceptedFacts } from './facts.js';
import { listLiveThreads } from './threads.js';
import { findLorebookEntryByComment, resolveNpcName } from './lorebook_v2.js';
import { log } from './logger.js';
import {
    ensureStoryStateShape,
    freshStoryState,
    getContext,
    readAuthorsNote,
    readStoryState,
    writeAuthorsNote,
    writeStoryState,
} from './util.js';

const RESPONSE_LENGTH_CAP_HEADER = 'Response length cap';
const RESPONSE_LENGTH_CAP_BODY = (
    'Cap your reply at the base prompt\'s length rules: 1–2 short paragraphs by default '
    + '(~80–120 words), 3 paragraphs only for scene transitions or climaxes. Never four.'
);

// --- Parsing / formatting (kept for user edits to the AN) ---------------

function normalizeHeading(label) {
    return label.trim().toLowerCase();
}

export function parseAuthorsNoteSections(text = readAuthorsNote(), sectionList = AUTHORS_NOTE_SECTIONS) {
    const normalizedLabels = new Map(sectionList.map((label) => [normalizeHeading(label), label]));
    const sections = Object.fromEntries(sectionList.map((label) => [label, '']));

    let currentLabel = null;
    const lines = stripResponseLengthCap(text).split('\n');

    for (const line of lines) {
        const headingMatch = line.match(/^([^:]+):\s*(.*)$/);
        const normalized = headingMatch ? normalizeHeading(headingMatch[1]) : null;
        if (normalized && normalizedLabels.has(normalized)) {
            currentLabel = normalizedLabels.get(normalized);
            sections[currentLabel] = headingMatch[2].trim();
            continue;
        }

        if (currentLabel) {
            sections[currentLabel] = `${sections[currentLabel]}\n${line}`.trim();
        }
    }

    return sections;
}

export function formatAuthorsNoteSections(sections, sectionList = AUTHORS_NOTE_SECTIONS) {
    return sectionList
        .map((label) => `${label}: ${String(sections[label] ?? '').trim()}`)
        .join('\n');
}

function stripResponseLengthCap(text) {
    const lines = String(text ?? '').split('\n');
    const headIdx = lines.findIndex((line) => line.trim().toLowerCase().startsWith(`${RESPONSE_LENGTH_CAP_HEADER.toLowerCase()}:`));
    if (headIdx < 0) return String(text ?? '');
    return lines.slice(0, headIdx).join('\n').trimEnd();
}

function appendResponseLengthCap(text) {
    return `${String(text ?? '').trimEnd()}\n\n${RESPONSE_LENGTH_CAP_HEADER}: ${RESPONSE_LENGTH_CAP_BODY}`.trim();
}

// --- Initialization ------------------------------------------------------

/**
 * If the current chat has no state document, seed a fresh v3 one. If it
 * has a v1/v2 document, archive it. Idempotent.
 */
export async function ensureStoryStateInitialized() {
    const context = getContext();
    if (!context.chatMetadata) return;
    const stored = readStoryState();
    if (!stored) {
        await writeStoryState(freshStoryState());
        return;
    }
    const version = Number(stored.schemaVersion ?? 0);
    if (version !== 3) {
        await archiveLegacyAndReset();
    }
}

async function archiveLegacyAndReset() {
    const context = getContext();
    const existing = readStoryState();
    if (!existing) return;
    const archive = context.chatMetadata?.solo_ttrpg_story_state_archive ?? [];
    archive.push({
        archivedAt: new Date().toISOString(),
        previousSchemaVersion: Number(existing.schemaVersion ?? 0) || null,
        state: existing,
    });
    context.chatMetadata.solo_ttrpg_story_state_archive = archive;
    await writeStoryState(freshStoryState());
    log('Archived v1/v2 story state and reset to v3.', 'info');
}

// --- v3 compatibility shim ----------------------------------------------

/**
 * In v2 this kicked off LLM calls to refresh AN summaries on a cadence.
 * In v3 the AN is purely deterministic, so this is a no-op preserved
 * for backwards-compat with the per-turn hook in index.js.
 */
export async function refreshSummariesSilently() {
    // Intentionally empty — see header comment.
}

// --- AN composition ------------------------------------------------------

/**
 * Re-render the Author's Note from the current state. Called after the
 * fact extractor commits, after a manual rewind, and on chat-load. The
 * resulting AN is small (under ~500 tokens) — no padding, no
 * placeholders for empty sections.
 */
export async function renderAuthorsNoteFromState() {
    const state = ensureStoryStateShape(readStoryState() ?? {});

    const sections = {};
    sections['Thematic spine'] = await readThematicSpineFromBible();
    sections['Live threads'] = composeLiveThreads(state);
    sections['Recent facts'] = composeRecentFacts(state);
    sections['Scene context'] = composeSceneContext(state);
    sections['On-screen NPCs'] = await composeOnScreenNpcs(state);
    sections["Director's notes"] = composeDirectorsNote(state);
    sections['Pressure cue'] = composePressureCue(state);
    sections['Tone reminders'] = await composeToneReminder();

    // Drop empty sections — the GM doesn't need to read placeholders.
    const compact = {};
    for (const label of AUTHORS_NOTE_SECTIONS) {
        const value = String(sections[label] ?? '').trim();
        if (value) compact[label] = value;
    }

    let rendered = formatAuthorsNoteSections(compact, Object.keys(compact));
    rendered = appendResponseLengthCap(rendered);
    await writeAuthorsNote(rendered);
    return rendered;
}

function composeLiveThreads(state) {
    const live = listLiveThreads(state, THREAD_LIMITS.liveThreadsInAN);
    if (live.length === 0) return '';
    return live.map((t) => `- ${t.question}`).join('\n');
}

function composeRecentFacts(state) {
    const recent = listRecentAcceptedFacts(state, FACT_LIMITS.recentFactsInAN);
    if (recent.length === 0) return '';
    return recent.map((f) => `- ${f.text}`).join('\n');
}

function composeSceneContext(state) {
    const parts = [];
    if (state.scene?.location) parts.push(`Where: ${state.scene.location}.`);
    if (state.scene?.tension) parts.push(`Tension: ${state.scene.tension}.`);
    return parts.join(' ');
}

async function composeOnScreenNpcs(state) {
    const ids = Array.isArray(state.scene?.presentNpcIds) ? state.scene.presentNpcIds : [];
    if (ids.length === 0) return '';
    const lines = [];
    for (const id of ids.slice(0, 6)) {
        const name = await resolveNpcName(id);
        const npc = state.npcs?.[id];
        const annotation = npc?.attitude ? ` — ${npc.attitude}` : '';
        lines.push(`- ${name}${annotation}`);
    }
    return lines.join('\n');
}

function composeDirectorsNote(state) {
    const note = state.directorsNotes?.active;
    if (!note) return '';
    const parts = [`- ${note.text}`];
    if (note.hint) parts.push(`  Reveal-eligible this scene only. Hint: ${note.hint}`);
    return parts.join('\n');
}

function composePressureCue(state) {
    const cue = state.pressureCue;
    if (!cue?.kind) return '';
    const label = cue.kind === 'lean-in' ? 'lean in'
        : cue.kind === 'let-it-breathe' ? 'let it breathe'
        : cue.kind === 'complication' ? 'introduce a complication'
        : cue.kind;
    return `- ${label}${cue.reason ? ` — ${cue.reason}` : ''}`;
}

async function composeToneReminder() {
    // We deliberately keep this short — the full overlay reaches the GM
    // via the lorebook entry __pack_gm_overlay; this is just a nudge
    // pointer.
    const overlayEntry = await findLorebookEntryByComment(PACK_LOREBOOK_ENTRIES.overlay);
    if (!overlayEntry) return '';
    return '- See __pack_gm_overlay for the genre voice and posture.';
}

async function readThematicSpineFromBible() {
    const bible = await findLorebookEntryByComment(PACK_LOREBOOK_ENTRIES.bible);
    if (!bible?.content) return '';
    const text = String(bible.content);
    const match = text.match(/(?:thematic\s+spine|escalation\s+themes)\s*:?\s*([^\n]+(?:\n\s+[^\n]+)*)/i);
    if (!match) return '';
    const block = match[1].trim();
    // Compress to the first 2 lines or 220 chars.
    const lines = block.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 2);
    const compact = lines.join(' ');
    return compact.length > 240 ? `${compact.slice(0, 239)}…` : compact;
}
