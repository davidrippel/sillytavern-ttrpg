// inline_ui.js — DOM injection for the v3 inline-first UX.
//
// Two pieces of UI live "in the chat" rather than in the extension's
// settings panel:
//
//   1. Fact chip strip — appears below every assistant message that
//      has provisional facts. Each chip is one extracted fact with
//      ✓ accept / ✎ edit / ✗ reject. Chips fade to "accepted" after
//      the next assistant message if untouched.
//
//   2. Threads tray — a single docked row at the top of the chat
//      surface. Shows live threads as small chips; click to expand
//      into a collapsible panel where threads can be renamed,
//      retired, or added manually.
//
// SillyTavern renders chat messages as `.mes` elements with a `mesid`
// data attribute. We attach our chip strip as a sibling block below
// the `.mes_block` so it sits flush against the message body.

import { acceptFact, editFact, FACT_STATUS, listProvisionalFacts, rejectFact } from './facts.js';
import { listAllActiveThreads, openThread, retireThread, renameThread, THREAD_STATUS } from './threads.js';
import { log } from './logger.js';
import { ensureStoryStateShape, escapeHtml, getSettings, readStoryState } from './util.js';

const CHIP_STRIP_CLASS = 'solo-fact-chips';
const TRAY_ID = 'solo-threads-tray';

/**
 * Render or refresh the fact chip strip under one specific message.
 * `mesId` is the SillyTavern message index (string).
 *
 * If `mesId` is null we fall back to the most-recent message — useful
 * for the just-extracted-now path.
 */
export function renderFactChipsForLatestMessage() {
    const settings = getSettings();
    if (settings.ui?.inlineFactChips === false) return;
    const $mes = $('#chat .mes').last();
    if ($mes.length === 0) return;
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const provisional = listProvisionalFacts(state);
    renderChipsInto($mes, provisional);
}

/**
 * Refresh chips on ALL messages — used after rewind or a state edit
 * from the settings panel where multiple messages may need re-rendering.
 */
export function refreshAllFactChips() {
    const settings = getSettings();
    if (settings.ui?.inlineFactChips === false) {
        $(`.${CHIP_STRIP_CLASS}`).remove();
        return;
    }
    const state = ensureStoryStateShape(readStoryState() ?? {});
    const provisional = listProvisionalFacts(state);

    // Group provisional facts by the turn they were extracted on. The
    // turn is monotonically aligned with assistant message order, so we
    // walk assistant `.mes` elements in order and slice.
    const byTurn = new Map();
    for (const fact of provisional) {
        const key = Number(fact.turn);
        if (!byTurn.has(key)) byTurn.set(key, []);
        byTurn.get(key).push(fact);
    }

    // Strip everything first; re-render targeted strips.
    $(`.${CHIP_STRIP_CLASS}`).remove();

    if (byTurn.size === 0) return;

    // We don't have a perfect mapping from turn → mes element, so just
    // attach all current provisional facts to the latest message. The
    // common case (single most-recent extraction) is what users see.
    const $latest = $('#chat .mes').last();
    if ($latest.length > 0) {
        renderChipsInto($latest, provisional);
    }
}

function renderChipsInto($mes, facts) {
    $mes.find(`.${CHIP_STRIP_CLASS}`).remove();
    if (!facts || facts.length === 0) return;

    const $strip = $('<div></div>')
        .addClass(CHIP_STRIP_CLASS)
        .attr('aria-label', 'Provisional facts extracted from this scene');

    for (const fact of facts) {
        const $chip = $('<span></span>').addClass('solo-fact-chip').attr('data-fact-id', fact.id);
        $chip.append(
            $('<span></span>').addClass('solo-fact-text').text(fact.text),
        );
        const $actions = $('<span></span>').addClass('solo-fact-actions');
        $actions.append(
            $('<button type="button" title="Accept"></button>')
                .addClass('solo-fact-btn solo-fact-accept')
                .text('✓')
                .on('click', () => handleAccept(fact.id, $chip)),
        );
        $actions.append(
            $('<button type="button" title="Edit"></button>')
                .addClass('solo-fact-btn solo-fact-edit')
                .text('✎')
                .on('click', () => handleEdit(fact.id, fact.text, $chip)),
        );
        $actions.append(
            $('<button type="button" title="Reject"></button>')
                .addClass('solo-fact-btn solo-fact-reject')
                .text('✗')
                .on('click', () => handleReject(fact.id, $chip)),
        );
        $chip.append($actions);
        $strip.append($chip);
    }

    const $target = $mes.find('.mes_block').first();
    if ($target.length > 0) {
        $target.append($strip);
    } else {
        $mes.append($strip);
    }
}

async function handleAccept(factId, $chip) {
    await acceptFact(factId);
    $chip.addClass('solo-fact-accepted').css('opacity', 0.55);
    setTimeout(() => $chip.remove(), 600);
}

async function handleReject(factId, $chip) {
    await rejectFact(factId);
    $chip.addClass('solo-fact-rejected').css('opacity', 0.4);
    setTimeout(() => $chip.remove(), 400);
}

async function handleEdit(factId, currentText, $chip) {
    // Lightweight inline edit via prompt(). Phase 2 ships with this
    // minimal UX; a richer modal can replace it in a later pass.
    const next = globalThis.prompt('Edit fact:', currentText);
    if (next === null) return;
    await editFact(factId, next);
    $chip.find('.solo-fact-text').text(next.trim() || currentText);
    $chip.addClass('solo-fact-edited');
}

// ---- Threads tray -------------------------------------------------------

export function renderThreadsTray() {
    const settings = getSettings();
    if (settings.ui?.threadsTray === false) {
        $(`#${TRAY_ID}`).remove();
        return;
    }

    const state = ensureStoryStateShape(readStoryState() ?? {});
    const live = listAllActiveThreads(state);

    let $tray = $(`#${TRAY_ID}`);
    if ($tray.length === 0) {
        $tray = $('<div></div>').attr('id', TRAY_ID).addClass('solo-threads-tray');
        const $anchor = $('#chat').parent();
        if ($anchor.length > 0) {
            $anchor.prepend($tray);
        } else {
            $('body').prepend($tray);
        }
    }

    $tray.empty();

    if (live.length === 0) {
        $tray.append(
            $('<span></span>').addClass('solo-tray-empty').text('No live threads yet.'),
        );
    } else {
        for (const thread of live) {
            const $chip = $('<span></span>')
                .addClass('solo-thread-chip')
                .attr('data-thread-id', thread.id)
                .toggleClass('solo-thread-escalating', thread.status === THREAD_STATUS.escalating)
                .toggleClass('solo-thread-resolved', thread.status === THREAD_STATUS.resolved)
                .text(thread.question);
            const $retire = $('<button type="button" title="Retire thread"></button>')
                .addClass('solo-thread-retire')
                .text('×')
                .on('click', async (e) => {
                    e.stopPropagation();
                    await retireThread(thread.id);
                    renderThreadsTray();
                });
            $chip.append($retire);
            $chip.on('click', () => promptRename(thread.id, thread.question));
            $tray.append($chip);
        }
    }

    const $add = $('<button type="button" title="Open a new thread"></button>')
        .addClass('solo-thread-add')
        .text('+ thread')
        .on('click', async () => {
            const q = globalThis.prompt('New thread (open dramatic question):', '');
            if (!q) return;
            const state = ensureStoryStateShape(readStoryState() ?? {});
            await openThread({ question: q, turn: state.turn });
            renderThreadsTray();
        });
    $tray.append($add);
}

async function promptRename(threadId, currentQuestion) {
    const next = globalThis.prompt('Rename thread:', currentQuestion);
    if (next === null) return;
    await renameThread(threadId, next);
    renderThreadsTray();
}
