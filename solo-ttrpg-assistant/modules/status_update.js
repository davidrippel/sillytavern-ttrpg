import { getActivePack } from './pack.js';
import { getCharacter, saveCharacter } from './sheet.js';
import { log } from './logger.js';
import { escapeHtml, getContext } from './util.js';

const STATUS_BLOCK_REGEX = /\[STATUS_UPDATE\]([\s\S]*?)\[\/STATUS_UPDATE\]/i;

function parseInventoryDelta(text) {
    return text
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean)
        .map((part) => ({
            op: part.startsWith('-') ? 'remove' : 'add',
            value: part.replace(/^[-+]/, '').trim(),
        }));
}

function parseLine(line) {
    const separatorIndex = line.indexOf(':');
    if (separatorIndex === -1) {
        return null;
    }

    const rawField = line.slice(0, separatorIndex);
    const rawValue = line.slice(separatorIndex + 1);
    const field = rawField.trim();
    const value = rawValue.trim();

    if (value.includes('->')) {
        const [from, to] = value.split('->').map((part) => part.trim());
        return { field, type: 'replace', from, to };
    }

    if (field === 'conditions' || field === 'inventory') {
        return { field, type: 'list_delta', values: parseInventoryDelta(value) };
    }

    return { field, type: 'raw', value };
}

export function parseStatusUpdateBlock(messageText) {
    const match = String(messageText ?? '').match(STATUS_BLOCK_REGEX);
    if (!match) {
        return null;
    }

    const lines = match[1]
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);

    const changes = lines.map(parseLine).filter(Boolean);
    return changes.length > 0 ? changes : null;
}

function applyThresholdConsequences(character, pack, triggeredKeys) {
    const notices = [];

    for (const key of triggeredKeys) {
        const resource = pack.resourceMap[key];
        if (!resource || resource.kind !== 'pool_with_threshold') {
            continue;
        }

        const currentValue = Number(character.state?.[key] ?? 0);
        const thresholdValue = resource.threshold_field
            ? Number(character.state?.[resource.threshold_field] ?? 0)
            : Number(resource.threshold ?? 0);

        if (!thresholdValue || currentValue < thresholdValue) {
            continue;
        }

        const consequence = resource.threshold_consequence;
        if (consequence?.field) {
            const current = Number(character.state?.[consequence.field] ?? 0);
            const delta = Number(String(consequence.delta ?? 0).replace('+', '')) || 0;
            character.state[consequence.field] = current + delta;
            notices.push(`${resource.display} crossed its threshold. ${consequence.field} changed by ${delta >= 0 ? '+' : ''}${delta}.`);
        }

        if (consequence?.then_reset) {
            character.state[key] = 0;
            notices.push(`${resource.display} reset to 0.`);
        }

        if (resource.threshold_effect) {
            notices.push(`Threshold effect: ${resource.threshold_effect}.`);
        }
    }

    return notices;
}

export function applyStatusChanges(changes) {
    const pack = getActivePack();
    const character = getCharacter();
    const changedKeys = new Set();
    const warnings = [];

    for (const change of changes) {
        const field = change.field;

        if (pack) {
            const supported = pack.resourceMap[field] || field === 'conditions' || field === 'inventory';
            if (!supported) {
                warnings.push(`Unknown field "${field}"`);
                continue;
            }
        }

        if (change.type === 'replace') {
            const nextValue = Number.isFinite(Number(change.to)) ? Number(change.to) : change.to;
            character.state[field] = nextValue;
            changedKeys.add(field);
            continue;
        }

        if (change.type === 'raw') {
            character.state[field] = Number.isFinite(Number(change.value)) ? Number(change.value) : change.value;
            changedKeys.add(field);
            continue;
        }

        if (change.type === 'list_delta' && field === 'conditions') {
            character.state.conditions ??= [];
            for (const entry of change.values) {
                if (entry.op === 'add' && !character.state.conditions.includes(entry.value)) {
                    character.state.conditions.push(entry.value);
                }
                if (entry.op === 'remove') {
                    character.state.conditions = character.state.conditions.filter((item) => item !== entry.value);
                }
            }
            changedKeys.add(field);
            continue;
        }

        if (change.type === 'list_delta' && field === 'inventory') {
            character.equipment ??= [];
            for (const entry of change.values) {
                if (entry.op === 'add' && !character.equipment.includes(entry.value)) {
                    character.equipment.push(entry.value);
                }
                if (entry.op === 'remove') {
                    character.equipment = character.equipment.filter((item) => item !== entry.value);
                }
            }
            changedKeys.add(field);
        }
    }

    const notices = pack ? applyThresholdConsequences(character, pack, [...changedKeys]) : [];
    saveCharacter();
    return { warnings, notices };
}

function summarizeChanges(changes) {
    return changes.map((change) => {
        if (change.type === 'replace') {
            return `<li><code>${escapeHtml(change.field)}</code>: ${escapeHtml(change.from)} -> ${escapeHtml(change.to)}</li>`;
        }
        if (change.type === 'list_delta') {
            return `<li><code>${escapeHtml(change.field)}</code>: ${escapeHtml(change.values.map((entry) => `${entry.op === 'add' ? '+' : '-'}${entry.value}`).join(', '))}</li>`;
        }
        return `<li><code>${escapeHtml(change.field)}</code>: ${escapeHtml(change.value ?? '')}</li>`;
    }).join('');
}

export async function maybeHandleStatusUpdate(message) {
    const changes = parseStatusUpdateBlock(message?.mes ?? message?.message ?? '');
    if (!changes || changes.length === 0) {
        return;
    }

    const context = getContext();
    const popup = new context.Popup(
        `<div class="solo-ttrpg-assistant solo-stack"><p>GM proposes these changes:</p><ul>${summarizeChanges(changes)}</ul><label class="solo-stack"><span>Edit before applying</span><textarea id="solo-status-edit" class="solo-code">${escapeHtml(changes.map((change) => {
            if (change.type === 'replace') {
                return `${change.field}: ${change.from} -> ${change.to}`;
            }
            return `${change.field}: ${change.values.map((entry) => `${entry.op === 'add' ? '+' : '-'}${entry.value}`).join(', ')}`;
        }).join('\n'))}</textarea></label></div>`,
        context.POPUP_TYPE.TEXT,
        'STATUS_UPDATE',
        {
            okButton: 'Accept',
            cancelButton: 'Ignore',
            wide: true,
        },
    );

    const result = await popup.show();
    if (result !== context.POPUP_RESULT.AFFIRMATIVE) {
        log('Ignored STATUS_UPDATE proposal.', 'info');
        return;
    }

    const edited = popup.dom?.querySelector?.('#solo-status-edit')?.value;
    const reparsed = edited
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map(parseLine)
        .filter(Boolean);

    const outcome = applyStatusChanges(reparsed);
    if (outcome.warnings.length > 0) {
        toastr.warning(outcome.warnings.join('\n'));
    }
    if (outcome.notices.length > 0) {
        toastr.info(outcome.notices.join('\n'));
    }
    log('Applied STATUS_UPDATE proposal.', 'info', { warnings: outcome.warnings, notices: outcome.notices });
}
