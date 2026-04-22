import { QR_SET_NAME } from './constants.js';
import { log } from './logger.js';
import { findAbilityDefinition, getActivePack, subscribePack } from './pack.js';
import { findAbilityOnSheet, getCharacter } from './sheet.js';
import { formatSignedNumber, getContext, isExtensionEnabled, normalizeName } from './util.js';

function roll2d6() {
    const die1 = Math.floor(Math.random() * 6) + 1;
    const die2 = Math.floor(Math.random() * 6) + 1;
    return { die1, die2, total: die1 + die2 };
}

function getResultBand(total) {
    if (total >= 10) {
        return 'full success';
    }
    if (total >= 7) {
        return 'partial success';
    }
    return 'failure with consequences';
}

async function appendSystemMessage(text) {
    const context = getContext();
    const message = {
        name: 'System',
        is_system: true,
        mes: text,
        extra: {
            type: 'system',
            isSmallSys: true,
        },
    };
    context.chat.push(message);
    context.addOneMessage(message);
    await context.saveChat();
}

function buildRollMessage(label, roll, modifier) {
    const total = roll.total + modifier;
    const modifierText = modifier ? ` ${modifier > 0 ? '+' : '-'} ${Math.abs(modifier)}` : '';
    return `[ROLL: ${label} - 2d6 (${roll.die1}+${roll.die2}=${roll.total})${modifierText} = **${total} - ${getResultBand(total)}**]`;
}

async function executeAttributeRoll(attributeKey) {
    if (!isExtensionEnabled()) {
        throw new Error('Solo TTRPG Assistant is disabled.');
    }

    const pack = getActivePack();
    const character = getCharacter();
    const attribute = pack?.attributeMap?.[attributeKey];
    const modifier = Number(character.attributes?.[attributeKey] ?? 0);
    const label = attribute ? `${attribute.display} check` : `${attributeKey} check`;
    const roll = roll2d6();
    const message = buildRollMessage(label, roll, modifier);
    await appendSystemMessage(message);
    log(`Rolled ${label}: ${roll.total} ${formatSignedNumber(modifier)} = ${roll.total + modifier}.`);
    return message;
}

async function executeManualRoll(modifier) {
    if (!isExtensionEnabled()) {
        throw new Error('Solo TTRPG Assistant is disabled.');
    }

    const roll = roll2d6();
    const message = buildRollMessage('Manual check', roll, modifier);
    await appendSystemMessage(message);
    log(`Rolled manual check: ${roll.total} ${formatSignedNumber(modifier)} = ${roll.total + modifier}.`);
    return message;
}

async function executeAbilityRoll(abilityName) {
    if (!isExtensionEnabled()) {
        throw new Error('Solo TTRPG Assistant is disabled.');
    }

    const pack = getActivePack();
    const sheetAbility = findAbilityOnSheet(abilityName);
    if (!sheetAbility) {
        throw new Error(`Ability "${abilityName}" is not on the sheet.`);
    }

    const sheetAbilityName = typeof sheetAbility === 'string' ? sheetAbility : sheetAbility.name;
    const abilityDefinition = findAbilityDefinition(sheetAbilityName, pack);
    if (!abilityDefinition) {
        throw new Error(`Ability "${sheetAbilityName}" is not in the active pack catalog.`);
    }

    const category = pack.abilityCategoryMap?.[abilityDefinition.category];
    const attributeKey = category?.roll_attribute;
    if (!attributeKey) {
        throw new Error(`Ability "${sheetAbilityName}" has no roll_attribute in its category.`);
    }

    const modifier = Number(getCharacter().attributes?.[attributeKey] ?? 0);
    const roll = roll2d6();
    const label = `${sheetAbilityName} (${pack.attributeMap?.[attributeKey]?.display ?? attributeKey})`;
    const message = buildRollMessage(label, roll, modifier);
    await appendSystemMessage(message);
    log(`Rolled ability ${sheetAbilityName} using ${attributeKey}.`);
    return message;
}

function registerCommand(command) {
    getContext().SlashCommandParser.addCommandObject(command);
}

function registerSlashCommands() {
    const context = getContext();
    const { SlashCommand, SlashCommandArgument, ARGUMENT_TYPE } = context;

    registerCommand(SlashCommand.fromProps({
        name: 'rollattr',
        callback: async (_, unnamedArgs) => executeAttributeRoll(String(unnamedArgs[0] ?? '')),
        unnamedArgumentList: [
            SlashCommandArgument.fromProps({
                description: 'attribute key',
                typeList: [ARGUMENT_TYPE.STRING],
                isRequired: true,
            }),
        ],
        returns: 'formatted roll result',
        helpString: '<div>Roll 2d6 plus the current value of an attribute from the character sheet.</div>',
    }));

    registerCommand(SlashCommand.fromProps({
        name: 'pbtaroll',
        callback: async (_, unnamedArgs) => executeManualRoll(Number(unnamedArgs[0] ?? 0)),
        unnamedArgumentList: [
            SlashCommandArgument.fromProps({
                description: 'modifier',
                typeList: [ARGUMENT_TYPE.NUMBER],
                isRequired: true,
            }),
        ],
        returns: 'formatted roll result',
        helpString: '<div>Roll 2d6 plus an ad-hoc modifier.</div>',
    }));

    registerCommand(SlashCommand.fromProps({
        name: 'rollability',
        callback: async (_, unnamedArgs) => executeAbilityRoll(String(unnamedArgs.join(' ') ?? '')),
        unnamedArgumentList: [
            SlashCommandArgument.fromProps({
                description: 'ability name',
                typeList: [ARGUMENT_TYPE.STRING],
                isRequired: true,
                acceptsMultiple: true,
            }),
        ],
        returns: 'formatted roll result',
        helpString: '<div>Roll the category attribute for an ability on the current sheet.</div>',
    }));
}

function syncQuickReplies() {
    const pack = getActivePack();
    const api = globalThis.quickReplyApi;

    if (!pack || !api || typeof api.createSet !== 'function' || typeof api.createQuickReply !== 'function') {
        return;
    }

    try {
        let set = api.getSetByName(QR_SET_NAME);
        if (!set) {
            set = api.createSet(QR_SET_NAME, { disableSend: false, placeBeforeInput: false, injectInput: false });
        }

        for (const attribute of pack.attributes) {
            const existing = api.getQrByLabel?.(QR_SET_NAME, attribute.display);
            const props = {
                message: `/rollattr ${attribute.key}`,
                title: `${attribute.display} roll`,
                isHidden: false,
            };
            if (existing) {
                api.updateQuickReply(QR_SET_NAME, attribute.display, props);
            } else {
                api.createQuickReply(QR_SET_NAME, attribute.display, props);
            }
        }

        const activeSets = api.settings?.config?.setList;
        if (Array.isArray(activeSets) && !activeSets.some((entry) => normalizeName(entry?.set?.name ?? entry?.name) === normalizeName(QR_SET_NAME))) {
            activeSets.push({ name: QR_SET_NAME, visible: true });
            api.settings.save?.();
        }

        log(`Quick Replies synced for ${pack.displayName}.`);
    } catch (error) {
        log('Quick Reply sync failed; using extension-local roll controls only.', 'warn', error.message);
    }
}

export function initDiceModule() {
    registerSlashCommands();
    subscribePack(() => syncQuickReplies());
    syncQuickReplies();
}
