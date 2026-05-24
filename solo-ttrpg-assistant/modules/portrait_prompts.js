// portrait_prompts.js — surfaces NPC image-gen prompts from the lorebook.
//
// The `image_generator` patches each campaign's lorebook with disabled
// entries whose `comment` is `NPC Image Prompt: <name>`. This module
// reads those entries via the existing world-info path and lets the
// user pick an NPC and copy the prompt to the clipboard.

import { loadAllLorebookEntries } from './lorebook_v2.js';
import { log } from './logger.js';

const COMMENT_PREFIX = 'NPC Image Prompt: ';
const EMPTY_MESSAGE = 'No portrait prompts in the active lorebook. Run image_generator to populate.';

let cachedPanelRoot = null;
let cachedPrompts = new Map();

function $panel() {
    return cachedPanelRoot;
}

async function loadPrompts() {
    const entries = await loadAllLorebookEntries();
    const map = new Map();
    for (const entry of entries) {
        const comment = String(entry?.comment ?? '');
        if (!comment.startsWith(COMMENT_PREFIX)) continue;
        const name = comment.slice(COMMENT_PREFIX.length).trim();
        if (!name) continue;
        const content = String(entry?.content ?? '').trim();
        if (!content) continue;
        // First match wins if a prompt is duplicated across books.
        if (!map.has(name)) map.set(name, content);
    }
    return map;
}

function renderDropdown() {
    const $sel = $panel().find('#solo-portrait-npc-select').empty();
    const names = [...cachedPrompts.keys()].sort((a, b) => a.localeCompare(b));
    if (names.length === 0) {
        $sel.append($('<option value="">— No portrait prompts found —</option>'));
        $panel().find('#solo-portrait-prompt').val(EMPTY_MESSAGE);
        return;
    }
    $sel.append($('<option value="">— Select NPC —</option>'));
    for (const name of names) {
        $sel.append($('<option></option>').attr('value', name).text(name));
    }
    $panel().find('#solo-portrait-prompt').val('');
}

async function refresh() {
    if (!$panel()) return;
    try {
        cachedPrompts = await loadPrompts();
    } catch (error) {
        cachedPrompts = new Map();
        log(`Portrait prompts load failed: ${error?.message ?? error}`, 'warn');
    }
    renderDropdown();
}

function handleSelectChange(event) {
    const name = String(event.target.value ?? '');
    const $textarea = $panel().find('#solo-portrait-prompt');
    if (!name) {
        $textarea.val(cachedPrompts.size === 0 ? EMPTY_MESSAGE : '');
        return;
    }
    $textarea.val(cachedPrompts.get(name) ?? '');
}

async function handleCopy() {
    const text = String($panel().find('#solo-portrait-prompt').val() ?? '');
    if (!text || text === EMPTY_MESSAGE) {
        toastr.warning('Nothing to copy. Select an NPC first.');
        return;
    }
    try {
        await navigator.clipboard.writeText(text);
        toastr.success('Prompt copied to clipboard.');
    } catch (error) {
        toastr.error(`Copy failed: ${error?.message ?? error}`);
    }
}

/**
 * Wire the Portrait Prompts card. Idempotent: safe to call once per
 * panel mount. The caller (`settings.js`) passes the cached panel root
 * jQuery object so we don't re-query the DOM.
 */
export function wirePortraitPromptsCard(panelRoot) {
    cachedPanelRoot = panelRoot;
    panelRoot.find('#solo-portrait-refresh').on('click', () => refresh());
    panelRoot.find('#solo-portrait-npc-select').on('change', handleSelectChange);
    panelRoot.find('#solo-portrait-copy').on('click', handleCopy);
    // Initial load — fire-and-forget; UI shows empty state until done.
    refresh();
}
