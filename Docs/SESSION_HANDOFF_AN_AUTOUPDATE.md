# Session Handoff — Author's Note Auto-Update

> **SUPERSEDED.** The over-keeping diff problem described below was
> resolved by replacing the user-driven Scene End / Act Transition flow
> with GM-emitted closure tags (`<<beat:LABEL:resolved>>`,
> `<<act:N:complete>>`, `<<clue:found:ID>>`) and a 2-beat AN window
> (Current beat + Next beat). See [04_EXTENSION_BRIEF.md](04_EXTENSION_BRIEF.md)
> §2.2 and [07_GM_BASE_PROMPT.md](07_GM_BASE_PROMPT.md) "Closure protocol"
> for the new design. The notes below are kept as historical context.

---


## Project context

**SillyTavern Solo TTRPG Assistant** — a SillyTavern extension for solo tabletop RPG play. The user (a solo player) roleplays a character; an LLM acts as the GM running an authored campaign. The extension manages character sheets, dice, canon detection, and (relevant here) Author's Note updates.

## The Author's Note system

The Author's Note has 5 sections, injected at depth 4 in every prompt:
- **Current Act** — current act header
- **Pending beats** — authored beats from the act not yet played out
- **Active threads** — emergent open subplots
- **Recent beats** — summary of last few scenes
- **Reminders** — situational pressures (countdowns, NPC conditions, etc.)

Two user-triggered flows in `solo-ttrpg-assistant/modules/authors_note.js`:
- **Scene End** — auto-generates Recent beats, Pending beats, Active threads, Reminders proposals via LLM, shows them in a confirmation popup for the user to review/edit before applying
- **Act Transition** — increments Current Act, regenerates Pending beats and Active threads for the new act

## What was built this session

1. **GM prompt hints** (`Docs/07_GM_BASE_PROMPT.md`) — GM now emits OOC hints when a scene's dramatic question is resolved or when an act's beats are all addressed, so the player knows when to click Scene End / Act Transition.

2. **Auto-generation of Pending beats / Active threads / Reminders** — previously only Recent beats was auto-generated. Added LLM-backed proposals for the other three so the user doesn't have to manually edit them.

3. **Switched from `generateQuietPrompt` → `generateRaw`** — `generateQuietPrompt` keeps the GM character's system prompt active, so the model would ignore our extraction prompts and write fiction. `generateRaw` lets us inject a clean "you are a structured-data extractor, not a GM" system prompt.

4. **Sanitizer** for proposals — strips out section headings, `---` separators, NPC dialogue blocks, narrative prose; requires bullet structure (or a sentinel like `(none)` / `(all beats resolved)`).

5. **ID-driven Pending beats flow** — instead of asking the model to copy beat text verbatim (which it kept abbreviating to just "1.1"), we now parse the act lorebook entry into structured beats with IDs, ask the model for a chain-of-evidence ANALYSIS per beat then a `PENDING: [1.2] [1.3]` line, and the extension reconstructs full beat bullets from the lorebook text by ID.

6. **`{{user}}` substitution** — beat text from the lorebook contains `{{user}}` placeholders; substitute via `getContext().substituteParams` both at beat expansion and on the final formatted popup text.

7. **Removed two hardcoded "structural" reminders** from the campaign generator's `campaign_generator/campaign_generator/stages/initial_an.py` — they were genre/structural directives polluting the now-runtime Reminders field. Also updated `campaign_generator/prompts/08_initial_an.md` to document the new policy.

8. **Taller popup** — flex layout with `min-height: 50vh` on the textarea so the user can actually see and edit the full AN.

9. **Diagnostic logging** — added warn-level logs whenever the sanitizer rejects a response or the Pending beats parser fails, with a 300-400 char preview of the raw model output. Also info-level log on successful Pending beats showing how many beats were kept.

## The current problem

After all the above, **Pending beats keeps over-keeping**: even when Recent beats clearly shows beats 1.1 and 1.2 were addressed (player woke up, found Polaroid, received invitation), the model returns `PENDING: [1.1] [1.2] [1.3]` and the user gets all three back as still-pending.

Other sections (Active threads, Recent beats, Reminders) now work well — those produce concrete, grounded output.

The current diff prompt for Pending beats lives in `solo-ttrpg-assistant/modules/authors_note.js` inside `generatePendingBeatsProposal`. It uses chain-of-evidence:
```
ANALYSIS [1.1]: <central event> | <quote from Recent events, or NOT FOUND> | ADDRESSED/PENDING
...
PENDING: [1.3]
```

We've iterated on the bias several times — first too aggressive (dropped too much), now too conservative (drops nothing). The recent fix added explicit guidance ("opening beats usually addressed in first scene; semantic match counts since Recent events is a summary"), but the user's last test still showed all 3 beats returned as pending.

## Where to pick up

The diagnostic logging from change #9 is the next data point. Run Scene End again and check the extension log panel for either:
- `Pending beats: kept 3 of 3 (PENDING: [1.1] [1.2] [1.3])` → confirms over-keeping is a prompt issue, need to push the model harder toward ADDRESSED
- `Pending beats: missing PENDING line` or `no resolvable IDs` → format failure, need a different output structure
- `Reminders: sanitizer rejected response. Raw preview: ...` → tells us what's being discarded for Reminders too

Without seeing the log, the next move is guesswork. With it, we'll know whether to fix the prompt, the parser, or the sanitizer.

## Key files touched this session

- `solo-ttrpg-assistant/modules/authors_note.js` — the bulk of the work (proposals, sanitizer, ID-driven flow, popup, logging)
- `Docs/07_GM_BASE_PROMPT.md` — added scene closure / act progression OOC hints
- `campaign_generator/campaign_generator/stages/initial_an.py` — removed hardcoded structural reminders
- `campaign_generator/prompts/08_initial_an.md` — documented Reminders-is-runtime-only policy
