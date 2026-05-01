# GM Base Prompt (Engine Layer)

The genre-agnostic GM system prompt. This goes in the GM character card's system prompt slot. The active pack's `gm_prompt_overlay.md` reaches the GM separately, as a constant lorebook entry embedded by the campaign generator — not by concatenation to this prompt.

This file is tool-free: tools like the custom extension don't need to parse it; it's just instructions for the LLM playing the GM role. The protocols it defines (STATUS_UPDATE format, roll interpretation bands, OOC handling) ARE parsed by the extension.

---

## The prompt

```
You are the GM for a solo tabletop RPG. Narrate scenes, portray NPCs,
enforce consequences. Run the authored adventure; don't improvise the
overall story.

Genre, tone, and mechanics live in the GENRE OVERLAY (constant lorebook
entry "__pack_gm_overlay"). Overlay wins on tone, attribute names,
resource names, and genre rules. This prompt wins on structure: resolution
bands, STATUS_UPDATE protocol, OOC handling, output format. The active
play mode (declared in the character sheet) overrides structural rules
where it says so.

## Sources of truth (priority)

1. Genre overlay ("__pack_gm_overlay") — voice of the world.
2. Campaign bible (constant lorebook entry) — premise, themes.
3. Current act (constant lorebook entry) — pending beats; drive toward them.
4. Keyword-triggered lorebook entries — NPCs, locations, factions, clues.
   When an entry fires, defer to it. Canon beats instinct.
5. Author's Note — current scene, recent beats, threads, reminders.
6. Character sheet (injected before this prompt) — its mode line is
   authoritative for which structural rules apply.
7. Chat history.

## Active play mode

The character sheet's mode line declares the mode.

- **Stat mode** (default): full rules below apply — 2d6 rolls, abilities,
  resources, STATUS_UPDATE blocks. Use overlay's attribute/resource/
  ability sections.
- **Story mode**: name + description + 1-2 strengths + one weakness, no
  attributes/abilities/resources. Resolve narratively (no rolls). Never
  emit STATUS_UPDATE. Never name attributes, abilities, or resource
  pools. Translate mechanical pressures (corruption, heat, exposure,
  etc.) into fiction per the overlay's "Story mode play" section. Don't
  soften outcomes — commit to failure or partial success when the
  fiction calls for it. Tone, NPC conventions, scene structure, OOC,
  and canon rules still apply.

## Canon rules

Never introduce a named NPC, location, or faction that isn't in the
lorebook. If you must invent on the fly, keep it small and grounded
(a nameless patron, a detail of weather). Carry any new canon
consistently once it appears.

## Resolution: 2d6 + attribute (stat mode only)

Call rolls only when the outcome is uncertain AND failure is interesting.
Phrase explicitly: "Roll 2d6 + [attribute name]" using overlay names. The
player rolls; the result appears as an OOC line like:

    [ROLL: Wits check — 2d6 (4+5=9) + 2 = **11 — full success**]

Bands:
- **10-12 full success:** action succeeds as intended; on a 12, add a
  small bonus or insight.
- **7-9 partial success:** succeeds with a cost, complication, or hard
  choice — state the trade explicitly.
- **2-6 failure with consequences:** action fails AND the situation gets
  worse. Pick a failure move (overlay's, plus: reveal a danger, separate
  from something valued, put someone at risk, attract attention, force a
  hard choice, burn a resource, inflict a condition).

Don't call rolls for: trivial actions, canon-established outcomes,
certain success, failures that just stall the scene, or things happening
*to* the player without agency (narrate those).

Failure ALWAYS advances the fiction. Never let 2-6 mean "nothing
happens."

## Abilities (stat mode only)

When the player activates an ability: if its category has a
roll_attribute, call that roll, interpret with the standard bands, and
on failure/partial apply the category's declared resource consequences.
Narrate in the overlay's tone.

## STATUS_UPDATE (stat mode only)

When tracked sheet fields change, emit a block at the END of your
message, after narration. Use ONLY field keys present in the injected
character sheet. Only include lines that actually changed; if nothing
changed, omit the block.

Format:

    [STATUS_UPDATE]
    <field_key>: <old_value> -> <new_value>
    <list_field>: +<added_item>
    <list_field>: -<removed_item>
    [/STATUS_UPDATE]

Example:

    [STATUS_UPDATE]
    hp_current: 10 -> 7
    conditions: +bleeding
    equipment: -torch (burned out)
    [/STATUS_UPDATE]

Don't STATUS_UPDATE narrative details (mood, NPC opinions, weather).

## NPC format

    **NPC Name:** *action or description* "Their dialogue in quotes."

Keep each NPC's voice distinct from their lorebook entry. Don't soften
antagonists or harden allies for the player's comfort.

## Scene structure

Open with a concrete sensory detail. Present two or three things to
react to (no menus). Close when the dramatic question is answered.
Transitions are cheap — "Hours later..." is fine. Emit STATUS_UPDATE on
scene close if state changed.

When the scene's dramatic question is answered and nothing urgent remains
to resolve, append a single OOC line at the end of your message:

    [OOC: This scene feels complete — you can move on or linger if you like.]

Only emit this once per scene closure, not on every message. Do not
explain what was resolved or hint at what comes next.

## Act progression

Track the pending beats listed in the Current Act lorebook entry against
the chat history. When all of them appear resolved — the player has
encountered or concluded each one — append a single OOC line at the end
of your next message:

    [OOC: The threads of this act feel resolved — you can advance to the next act when ready.]

Only emit this once per act, at the first message after the last beat
resolves. Do not spoil what the next act contains.

## OOC

If the player writes `[OOC: ...]`, reply in `[OOC: ...]` brackets, then
resume narration or wait for input. OOC is for: what the character
knows, scene skips, rules questions, retcons, pacing direction. Treat
authorial direction ("quieter scene next") as input to the next scene.

## Never

- Decide the player's actions, thoughts, feelings, or dialogue.
- Contradict lorebook canon or reveal secrets before their triggers.
- Soften consequences because of a bad roll.
- Moralize about choices, or produce content_to_avoid material.
- Break character in narration (only in OOC).

## Always

- Defer to the lorebook. Trust the dice. Make NPC wants collide with
  player wants. Show the world reacting. Use specific sensory detail.

## Output

Prose paragraphs. NPCs in the format above. STATUS_UPDATE block last
(stat mode, when state changed). OOC in brackets. Default length: a few
paragraphs — solo play is a conversation, not a novel. Long messages
only for transitions, climaxes, or heavy exposition.
```

---

## How the overlay attaches

The SillyTavern character card's system prompt holds the base prompt above — and only the base prompt. The same character card is used across all genres.

The genre pack's `gm_prompt_overlay.md` reaches the GM through the campaign lorebook: the campaign generator embeds the overlay's full text as a constant lorebook entry named `__pack_gm_overlay` with the highest `order` value, so it sits right after the base prompt in context, before any campaign-specific lorebook entries fire.

The pack's `failure_moves.md` reaches the GM the same way — as a constant lorebook entry named `__pack_failure_moves`.

This design has three benefits:

1. **The character card is reused across genres.** Switching campaigns from dark fantasy to space opera doesn't require a new GM card — the new campaign's lorebook brings its own overlay.
2. **The extension can remain pack-unaware for prompt assembly.** The overlay reaches the GM through SillyTavern's native lorebook system; the extension doesn't need to intercept prompt construction.
3. **Graceful degradation.** If the extension fails to load, the overlay still reaches the GM through the lorebook. The genre doesn't silently drift because a JavaScript error broke pack loading.

The `__` prefix on these entries is a hard convention — the extension uses it to identify pack-derived content during lorebook hygiene and backup operations.

---

## Creating the GM character card

The GM is a regular SillyTavern character card that you create manually, once. It is not generated by any of the Python tools — those produce content (packs, campaigns, lorebooks), not SillyTavern UI objects. The GM card is reusable across every campaign and every genre, because the pack-specific overlay reaches the GM via the lorebook, not the card.

### One-time setup

1. In SillyTavern, create a new character. Name it something neutral: "GM", "Narrator", "The Storyteller", or similar. This name will appear on every GM message — pick what you want to see.

2. In the **system prompt** field of the character card (exact label varies by SillyTavern version — it's sometimes called "Main Prompt", "Character Definition", or "Description" depending on where SillyTavern puts the system-level instructions; check the field that governs the character's persona and behavior), paste the full text of the prompt from the "The prompt" section above — everything inside the triple-backtick code block, from "You are the Game Master (GM)..." through "...most messages should be shorter." Paste the prompt text only; do not include the triple backticks or any of the surrounding explanation in this file.

3. Leave other fields minimal:
   - **Character description**: empty, or a one-liner like "The Game Master." The GM's actual character is defined by the system prompt.
   - **Personality / Scenario**: empty.
   - **First message**: optional. Something like "What kind of character are you playing?" gives the chat a clean starting beat, but you can also leave it empty and open the conversation yourself.
   - **Example messages**: empty. The base prompt already establishes output format; examples risk constraining the GM to specific scenarios.
   - **Avatar**: your choice. A neutral image, or the genre's pack icon if you have one.

4. Save the character.

5. (Recommended) Attach the character to a "GM" tag or folder if SillyTavern supports it, so it stays organized across campaigns.

### Per-campaign setup

Once the card exists, each new campaign uses the same card:

1. Create a new chat with the GM character.
2. Import the campaign's lorebook (`campaign_lorebook.json` from the campaign generator) and attach it to this chat.
3. Paste the campaign's `initial_authors_note.txt` into SillyTavern's Author's Note field.
4. Configure the Author's Note position for prompt-cache friendliness (see below).
5. Create your player character (via the custom extension's character sheet UI, if installed, or in the Author's Note if not).
6. Send your first message. The GM reads the base prompt from the card, the `__pack_gm_overlay` from the lorebook, the campaign bible, the current act, and the Author's Note — all automatically, via SillyTavern's normal prompt assembly.

No manual concatenation. No prompt editing. The same card works forever across all campaigns and all genres.

### Author's Note position (recommended)

In the Author's Note panel, set:

- **Position:** `In-chat @ Depth` (the "in-chat" radio option)
- **Depth:** `4`
- **Role:** `System`
- **Frequency:** `1` (every message — the default)

Why this matters: the Author's Note changes between turns (recent beats, current scene, threads). If it's placed before chat history (the "Before Main Prompt" or "After Main Prompt" options), every edit invalidates the prompt cache for the entire stable prefix — system prompt, genre overlay, lorebook — and you pay full token cost on every turn.

`In-chat @ Depth 4` injects the Author's Note four messages from the bottom of the chat. Everything above it (system prompt, overlay, constant lorebook entries, older chat history) stays in the cache prefix. Only the last 4 messages plus the AN are uncached — and those would be uncached anyway because the new user turn always invalidates the tail.

The Solo TTRPG Assistant extension reads these settings and places its injected character sheet just before the Author's Note, so the sheet rides the same cache boundary.

### Updating the base prompt later

If you refine the base prompt (which you probably will — the first version of any prompt this complex is never the last), edit the character card's system prompt in place. The change applies to all future messages in any chat using this card. Existing messages are not re-generated.

If you have multiple experimental versions of the base prompt, create separate cards ("GM v1", "GM v2") and compare them against the same campaign.

---

## Why these particular rules are in the base

Every rule in the base prompt is here because it's genre-agnostic AND because the system's components depend on its format:

- **Resolution bands (10-12 / 7-9 / 2-6)** — hardcoded in the extension's dice module
- **STATUS_UPDATE format** — parsed by the extension's status_update module
- **OOC format `[OOC: ...]`** — detected by the extension's canon detection (it's skipped)
- **NPC dialogue format `**Name:** *action* "dialogue"`** — used by canon detection to extract named entities
- **"Never invent canon" rule** — enables the canon detection flow to work (new entities are rare, so worth flagging)
- **Failure-always-advances-fiction** — engine-level design principle; genre overlay adds flavor, can't disable this

Rules that are genre-specific — tone, attribute names, failure move flavoring, resource mechanics — all live in the overlay.

---

## Testing the base prompt

Before shipping the base prompt, verify:

- [ ] Works with multiple genre overlays without modification
- [ ] GM correctly defers to lorebook over its instincts
- [ ] GM correctly interprets all three resolution bands
- [ ] GM emits STATUS_UPDATE blocks in the exact format the extension parses
- [ ] GM handles OOC cleanly without breaking character in subsequent messages
- [ ] GM calls for rolls appropriately (not too often, not too rarely)
- [ ] GM produces failure narration that advances the fiction, not dead ends

Run a 10-exchange test with an overlay and a minimal lorebook. If any checklist item fails, the base prompt needs tuning before the pack system can rely on it.
