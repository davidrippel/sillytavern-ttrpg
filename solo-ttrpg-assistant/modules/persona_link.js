import { linkPersona, syncPersonaForCharacter } from './characters.js';
import { escapeHtml, getContext, getCurrentPersonaKeySync, getPersonasMap } from './util.js';

function getPersonaEntries() {
    return Object.entries(getPersonasMap()).map(([key, name]) => ({ key, name: String(name ?? key) }));
}

export function getPersonaLinkInfo(character) {
    const personas = getPersonasMap();
    const linkedKey = character?.personaKey ?? null;
    const linkedName = linkedKey ? personas[linkedKey] ?? null : null;
    const currentKey = getCurrentPersonaKeySync();
    const currentName = currentKey ? personas[currentKey] ?? currentKey : null;

    if (!linkedKey) {
        return {
            label: 'Not linked',
            detail: currentName ? `Current SillyTavern persona: ${currentName}` : 'Choose a persona for auto-switching.',
            linkedKey: null,
            linkedName: null,
            currentKey,
            currentName,
            missing: false,
            synced: false,
        };
    }

    if (!linkedName) {
        return {
            label: 'Missing persona',
            detail: `Stored link: ${linkedKey}`,
            linkedKey,
            linkedName: null,
            currentKey,
            currentName,
            missing: true,
            synced: false,
        };
    }

    return {
        label: linkedName,
        detail: currentKey === linkedKey
            ? 'Auto-switch is in sync with the active persona.'
            : (currentName ? `Current SillyTavern persona: ${currentName}` : 'This persona is linked for auto-switching.'),
        linkedKey,
        linkedName,
        currentKey,
        currentName,
        missing: false,
        synced: currentKey === linkedKey,
    };
}

export async function promptPersonaLink(character) {
    if (!character?.id) {
        return false;
    }

    const context = getContext();
    const personas = getPersonaEntries();
    const currentKey = character.personaKey ?? '';
    let nextKey = currentKey;

    const wrapper = document.createElement('div');
    wrapper.className = 'solo-ttrpg-assistant solo-stack';

    const intro = document.createElement('p');
    intro.textContent = 'Choose which SillyTavern persona should follow this character.';
    wrapper.append(intro);

    const label = document.createElement('label');
    label.className = 'solo-stack';

    const labelText = document.createElement('span');
    labelText.textContent = 'Persona';
    label.append(labelText);

    const select = document.createElement('select');
    select.className = 'text_pole wide100p';
    select.innerHTML = `<option value="">${escapeHtml('-- None --')}</option>`;

    for (const persona of personas) {
        const option = document.createElement('option');
        option.value = persona.key;
        option.textContent = persona.name;
        option.selected = persona.key === currentKey;
        select.append(option);
    }

    if (currentKey && !personas.some((persona) => persona.key === currentKey)) {
        const option = document.createElement('option');
        option.value = currentKey;
        option.textContent = `Missing persona (${currentKey})`;
        option.selected = true;
        select.append(option);
    }

    select.addEventListener('change', () => {
        nextKey = select.value;
    });

    label.append(select);
    wrapper.append(label);

    const popup = new context.Popup(wrapper, context.POPUP_TYPE.CONFIRM, '', {
        okButton: 'Save',
        cancelButton: 'Cancel',
    });
    const result = await popup.show();

    if (result !== context.POPUP_RESULT.AFFIRMATIVE) {
        return false;
    }

    linkPersona(character.id, nextKey || null);
    return true;
}

export async function syncPersonaLink(character) {
    await syncPersonaForCharacter(character);
}
