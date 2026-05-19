// facts_extractor.js — the v3 replacement for scene_analyzer.js.
//
// After each assistant turn we run one LLM call that reads the prose
// the GM just wrote and proposes:
//
//   - new_facts:      atomic statements the prose established. Each
//                     carries a `sourceQuote` lifted verbatim from
//                     the prose, used for substring validation.
//   - thread_updates: status changes for existing threads ("advanced",
//                     "resolved", "escalating").
//   - new_threads:    open dramatic questions the player started
//                     pursuing this turn.
//   - truths_touched: campaign truths whose discovery surfaces were
//                     brushed by the prose (used by the pacing module
//                     to decide if a director's note has "landed").
//   - scene_delta:    optional updates to location / present NPCs /
//                     tension. The AN composer reads this.
//   - npc_state:      light per-NPC updates {lastSeenTurn, attitude}.
//
// The extractor *proposes*; it does not commit anything to canon by
// itself. The per-turn hook in index.js writes the facts as
// `provisional` (so the inline chip strip can render accept/edit/reject
// affordances) and applies the rest of the diff to state directly
// since threads/scene/npcs are recoverable via rewind.

import {
    getContext,
    getSettings,
    safeJsonParse,
} from './util.js';
import { log } from './logger.js';

const SYSTEM_PROMPT = [
    'You are a fact extractor for a tabletop RPG engine.',
    'You are NOT a game master. You do NOT narrate, write fiction, or roleplay.',
    "You read the latest GM narration and extract what was established in fiction.",
    'Output STRICT JSON only — no prose, no markdown fences, no comments.',
    'Be conservative: prefer omitting an uncertain fact over inventing one.',
].join(' ');

const MAX_FACTS = 5;
const MIN_QUOTE_CHARS = 8;

/**
 * Run the extractor LLM against the latest assistant message.
 *
 * Returns a normalised payload (always defined fields). On any failure
 * — LLM unavailable, JSON malformed, all facts fail quote validation —
 * the payload is empty but the hook still proceeds.
 */
export async function extractFromAssistantMessage({
    assistantMessageText,
    userMessageText = '',
    state,
    recentFactsLines = [],
    liveThreadsLines = [],
    sceneContextLine = '',
    onScreenNpcsLine = '',
    truthsForExtractor = [],
}) {
    const empty = {
        ran: false,
        newFacts: [],
        threadUpdates: [],
        newThreads: [],
        truthsTouched: [],
        sceneDelta: null,
        npcState: [],
        notes: '',
    };

    const settings = getSettings();
    if (settings.factExtractor?.enabled === false) {
        return empty;
    }

    const prose = String(assistantMessageText ?? '').trim();
    if (!prose) return empty;

    const prompt = buildPrompt({
        prose,
        userMessage: String(userMessageText ?? '').trim(),
        recentFactsLines,
        liveThreadsLines,
        sceneContextLine,
        onScreenNpcsLine,
        truthsForExtractor,
        turn: state?.turn ?? 0,
    });

    const raw = await runExtractorLLM(prompt);
    if (!raw) return empty;

    const json = parseJsonBlock(raw);
    if (!json || typeof json !== 'object') {
        log(
            `Fact extractor: response was not JSON; skipping. Raw (first 400 chars): ${truncate(raw, 400)}`,
            'warn',
        );
        return { ...empty, ran: true, notes: 'extractor JSON parse failed' };
    }

    const validatedFacts = [];
    for (const draft of Array.isArray(json.new_facts) ? json.new_facts.slice(0, MAX_FACTS) : []) {
        const text = String(draft?.text ?? '').trim();
        const quote = String(draft?.source_quote ?? '').trim();
        if (!text) continue;
        if (!quoteAppearsInProse(quote, prose)) {
            log(`Fact extractor: dropped fact with unverifiable quote: ${truncate(text, 80)}`, 'warn');
            continue;
        }
        validatedFacts.push({
            text,
            sourceQuote: quote,
            entities: Array.isArray(draft.entities) ? draft.entities.slice(0, 8) : [],
        });
    }

    const threadUpdates = Array.isArray(json.thread_updates)
        ? json.thread_updates
              .map((u) => ({
                  threadId: String(u?.thread_id ?? '').trim(),
                  status: normaliseThreadStatus(u?.status),
                  why: String(u?.why ?? '').trim() || null,
              }))
              .filter((u) => u.threadId)
        : [];

    const newThreads = Array.isArray(json.new_threads)
        ? json.new_threads
              .map((t) => ({
                  question: String(t?.question ?? '').trim(),
                  why: String(t?.why ?? '').trim() || null,
              }))
              .filter((t) => t.question.length > 0)
              .slice(0, 3)
        : [];

    const truthsTouched = Array.isArray(json.truths_touched)
        ? json.truths_touched
              .map((t) => ({
                  truthId: String(t?.truth_id ?? '').trim(),
                  how: String(t?.how ?? '').trim() || null,
              }))
              .filter((t) => t.truthId)
        : [];

    const npcState = Array.isArray(json.npc_state)
        ? json.npc_state
              .map((n) => ({
                  id: String(n?.id ?? '').trim(),
                  attitude: n?.attitude ? String(n.attitude).trim() : null,
                  status: n?.status ? String(n.status).trim() : null,
              }))
              .filter((n) => n.id)
        : [];

    const sceneDelta = json.scene_delta && typeof json.scene_delta === 'object'
        ? {
            location: json.scene_delta.location ? String(json.scene_delta.location).trim() : null,
            presentNpcIds: Array.isArray(json.scene_delta.present_npc_ids)
                ? json.scene_delta.present_npc_ids.map((s) => String(s).trim()).filter(Boolean)
                : null,
            tension: json.scene_delta.tension ? String(json.scene_delta.tension).trim() : null,
        }
        : null;

    return {
        ran: true,
        newFacts: validatedFacts,
        threadUpdates,
        newThreads,
        truthsTouched,
        sceneDelta,
        npcState,
        notes: String(json.notes ?? '').trim(),
    };
}

function buildPrompt({
    prose,
    userMessage,
    recentFactsLines,
    liveThreadsLines,
    sceneContextLine,
    onScreenNpcsLine,
    truthsForExtractor,
    turn,
}) {
    const truthsBlock = (truthsForExtractor ?? []).slice(0, 12).map(
        (t) => `- id: ${t.id} | text: ${truncate(t.text, 180)}`,
    );

    return [
        `Turn: ${turn}`,
        '',
        'Latest GM narration (this is the prose to extract from):',
        '"""',
        prose,
        '"""',
        '',
        'Player message that preceded it (context only — do not extract from this):',
        '"""',
        userMessage || '(none)',
        '"""',
        '',
        'Recent accepted facts (already in canon — do NOT re-extract these):',
        recentFactsLines.length ? recentFactsLines.join('\n') : '(none yet)',
        '',
        'Live threads (open dramatic questions):',
        liveThreadsLines.length ? liveThreadsLines.join('\n') : '(none yet)',
        '',
        'Scene context:',
        sceneContextLine || '(no scene set yet)',
        '',
        'On-screen NPCs:',
        onScreenNpcsLine || '(none)',
        '',
        'Campaign truths the system is tracking (the GM does NOT see these directly; mark any whose substance landed in the prose):',
        truthsBlock.length ? truthsBlock.join('\n') : '(none authored)',
        '',
        'Rules:',
        `- Output at most ${MAX_FACTS} new facts. Each fact is one atomic declarative statement.`,
        '- Every fact MUST carry `source_quote` — a substring from the GM narration that proves the fact landed. The runtime rejects facts whose quote does not appear verbatim in the prose.',
        '- Do not extract facts the player merely speculated about. Extract only what the GM\'s prose established.',
        '- Do not duplicate items already in Recent facts.',
        '- Open a new thread only when the player\'s actions in the prose introduce a new pursuit. Keep questions short ("Who killed Eda?").',
        '- Update existing threads when prose visibly advanced them. Use `thread_id` from Live threads.',
        '- Mark a campaign truth as `truths_touched` only if the prose surfaces its substance (a discovery surface). Mentioning an NPC by name is not enough.',
        '- Update `npc_state` only when the prose shows an attitude shift or status change.',
        '- `scene_delta` is optional. Use it when location/present-NPCs/tension visibly changed.',
        '',
        'Output schema (STRICT JSON, no markdown, no prose):',
        '{',
        '  "new_facts": [ { "text": "...", "source_quote": "...", "entities": ["..."] } ],',
        '  "thread_updates": [ { "thread_id": "...", "status": "live|escalating|resolved", "why": "..." } ],',
        '  "new_threads": [ { "question": "...", "why": "..." } ],',
        '  "truths_touched": [ { "truth_id": "...", "how": "..." } ],',
        '  "scene_delta": { "location": "...", "present_npc_ids": ["..."], "tension": "..." } | null,',
        '  "npc_state": [ { "id": "...", "attitude": "...", "status": "..." } ],',
        '  "notes": "one short line of reasoning"',
        '}',
    ].join('\n');
}

async function runExtractorLLM(prompt) {
    const context = getContext();
    const generate = context.generateRaw;
    if (typeof generate !== 'function') {
        log('Fact extractor skipped — generateRaw unavailable.', 'warn');
        return '';
    }
    try {
        const result = await generate({
            prompt,
            systemPrompt: SYSTEM_PROMPT,
            instructOverride: true,
        });
        return String(result ?? '');
    } catch (error) {
        log('Fact extractor LLM call failed.', 'warn', error?.message ?? String(error));
        return '';
    }
}

function parseJsonBlock(raw) {
    const text = String(raw ?? '').trim();
    if (!text) return null;
    const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    const body = fenced ? fenced[1] : text;
    const first = body.indexOf('{');
    const last = body.lastIndexOf('}');
    if (first < 0 || last < first) return null;
    return safeJsonParse(body.slice(first, last + 1), null);
}

function normalise(text) {
    return String(text ?? '')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .replace(/[‘’‚‛]/g, "'")
        .replace(/[“”„‟]/g, '"')
        .replace(/[–—]/g, '-')
        .trim();
}

/**
 * The quote-validation gate: the extractor's `source_quote` must appear
 * (verbatim, after whitespace + smart-punct normalisation) in the
 * narration prose. Loose substring matching from the v2 analyzer is
 * intentionally narrowed here — if the model paraphrases the prose,
 * we drop the fact. Better to lose a real fact than to commit a
 * hallucinated one.
 */
export function quoteAppearsInProse(quote, prose) {
    const q = normalise(quote);
    if (!q || q.length < MIN_QUOTE_CHARS) return false;
    const p = normalise(prose);
    return p.includes(q);
}

function normaliseThreadStatus(status) {
    const allowed = new Set(['live', 'escalating', 'resolved']);
    const lower = String(status ?? '').toLowerCase();
    return allowed.has(lower) ? lower : 'live';
}

function truncate(text, max) {
    const s = String(text ?? '').trim();
    if (s.length <= max) return s;
    return `${s.slice(0, max - 1)}…`;
}
