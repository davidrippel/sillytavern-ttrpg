# Solo TTRPG Assistant — SillyTavern Extension Brief

Build a SillyTavern extension that automates player-side maintenance for a solo narrative TTRPG campaign. Pack-aware: reads genre pack metadata at runtime so attributes, resources, and abilities match whichever pack the player is using.

Hand this file to Claude Code along with `01_SYSTEM_OVERVIEW.md`, `02_GENRE_PACK_SPEC.md`, and `07_GM_BASE_PROMPT.md` for context.

---

## Goal

Automate the repetitive maintenance tasks in a solo campaign while keeping the player in control of every change. Every automated action is a suggestion; the player confirms.

Core modules:

- Character sheet (pack-aware, structured, always in context)
- Dice rolling integrated with the 2d6+attribute resolution system
- Author's Note management (recent beats, active threads, act transitions)
- Canon detection (new NPCs, locations, items surfaced in GM messages)
- Backup and restore bundles
- Session log export
- Lorebook hygiene

---

## Tech stack

- JavaScript (ES modules), following the current SillyTavern extension template
- Uses SillyTavern's extension API, event system, and slash commands
- Minimal external dependencies — bundle only what's strictly necessary. Required: a YAML parser (`js-yaml` is the standard choice; bundle it, don't CDN-load) for reading pack YAML files. Required: a ZIP library (`jszip` is standard) for the backup/restore bundle. Everything else should use the platform (`File.text()`, `JSON.parse`, `fetch`, etc.)
- UI panels use SillyTavern's existing styling (import their CSS vars)
- Persistent storage via `extension_settings[extensionName]`

Web search during development: current SillyTavern extension docs, current event names (they change between versions), current World Info API surface, current Author's Note API.

---

## Pack loading — critical

The extension reads the active genre pack at runtime to parameterize its behavior. Attributes, resources, and abilities are never hardcoded. The loading mechanism is concrete and works entirely within the browser, with no companion server, no bundling step, and no filesystem access beyond what the user explicitly provides.

### Loading mechanism: directory picker

The extension's settings panel includes a "Load pack" button backed by an HTML `<input type="file" webkitdirectory multiple>`. When the user clicks it, the browser opens a directory picker; the user selects the pack's directory (e.g., `genres/symbaroum_dark_fantasy/`). The browser hands the extension a `FileList` containing every file in that directory. The extension:

1. Iterates the `FileList` looking for the 5 files it cares about (by exact filename)
2. Reads each file's text content (`File.text()`)
3. Parses YAML files with a bundled YAML library (`js-yaml` or equivalent) and JSON files with `JSON.parse`
4. Validates the parsed content against the schema in `02_GENRE_PACK_SPEC.md`
5. Stores the parsed structured data in `extension_settings[extensionName].activePack`
6. Displays a confirmation in the settings panel showing the loaded pack's `display_name`, `version`, and `description`

Files the extension does not read are simply ignored (they serve other consumers — the Python tools and the GM via the lorebook).

The 5 files the extension reads:
- `pack.yaml` → name, version, display_name (for the compatibility check, described below)
- `attributes.yaml` → the six attribute keys and display names (drives dice commands, sheet UI labels)
- `resources.yaml` → resource keys and kinds (drives sheet state UI, STATUS_UPDATE field whitelist, threshold logic)
- `abilities.yaml` → ability catalog and category definitions (drives the "add ability from catalog" UI)
- `character_template.json` → starting sheet shape (used when initializing a new character)

If any of these 5 files is missing or fails to parse, loading fails with a specific error message naming the file. The extension refuses to partially load a pack.

### Persistence

The parsed pack is stored in `extension_settings[extensionName].activePack` as structured JSON. This persists across SillyTavern sessions — the user loads a pack once and it sticks. No need to re-pick the directory every session.

### Multiple packs

The extension supports multiple loaded packs under `extension_settings[extensionName].packs`, keyed by `pack_name`. One is marked as `activePackName`. Loading a new pack via the directory picker stores it under its own name without clobbering others.

A dropdown in the settings panel lets the user switch which pack is active. Switching packs triggers a pack-compatibility check against the currently-open campaign (see below).

### Campaign compatibility check

Every campaign lorebook produced by the campaign generator includes a constant entry named `__pack_reference` containing the pack name and version the campaign was built against. This entry is marked `constant: false` with no trigger keywords — it never enters the GM's context; it exists purely as metadata for the extension to read via SillyTavern's World Info API.

On chat open (`CHAT_CHANGED` event) and on manual pack switch, the extension:

1. Reads `__pack_reference` from the current chat's active lorebook, if present
2. Compares against the currently-active pack's name and version
3. If they match: proceed silently
4. If name mismatches: display a non-blocking warning — "This campaign was built for pack `<expected>`, but you have `<active>` loaded. Dice rolls and the character sheet may not work correctly. Load the correct pack?" — with buttons to open the directory picker or dismiss
5. If name matches but version mismatches: display a softer warning — "This campaign was built for `<expected>@<old_version>`, you have `<active>@<new_version>`. Schema should be compatible but content may have shifted." — dismissible

If no `__pack_reference` entry exists (older campaigns, hand-built lorebooks), proceed silently. The extension makes no assumptions.

### Degraded mode (no pack loaded)

If no pack is loaded, the extension operates in a minimal "unknown pack" mode:
- Dice commands require manual modifier entry (`/pbtaroll <mod>`)
- The sheet UI renders a generic shape (name, concept, notes, and a free-form key/value table for user-defined attributes and state)
- The STATUS_UPDATE parser accepts any field name (no whitelist)
- The ability catalog UI is hidden

This mode exists so the extension doesn't hard-fail on fresh installs before the user loads a pack. It's not meant for sustained use.

### Reload

A "Reload pack" button in the settings panel re-opens the directory picker for the currently-active pack's name. Useful when the user has edited pack files on disk (e.g., tuned the GM overlay, added an ability) and wants the extension to pick up changes.

Note: changes to `gm_prompt_overlay.md` or `failure_moves.md` do NOT propagate to existing campaigns via a reload, because those files reach the GM through lorebook entries embedded by the campaign generator at campaign-creation time. To propagate overlay changes to an existing campaign, the user must regenerate the campaign OR manually edit the `__pack_gm_overlay` lorebook entry. The extension surfaces this in the reload confirmation: "Pack reloaded. Note: GM overlay changes apply to new campaigns only."

---

## Features (priority order for implementation)

### Tier 1 — Build first (minimum viable)

#### 1.1 Character sheet module

Maintain a structured character sheet in `extension_settings[extensionName].character`.

Schema is defined by the active pack's `character_template.json`. The extension does not assume specific field names beyond `name`, `concept`, `attributes`, `abilities`, `equipment`, `state`, `notes`.

**UI panel** (sidebar):
- Renders all sections of the sheet based on pack schema
- Attribute section: six rows, one per attribute from `attributes.yaml`, showing display name + current value + edit controls
- State section: one row per resource from `resources.yaml`, formatted according to `kind` (pool bar for `pool`, counter for `counter`, threshold indicator for `pool_with_threshold`)
- Abilities section: list with add/remove/edit; "Add from catalog" button pulls from pack's `abilities.yaml`
- Equipment: simple list with add/remove
- Notes: free text
- Auto-save on every change

**Prompt injection:**
At generation time, inject a compact formatted version of the sheet into the prompt. Configurable position (default: just before Author's Note). Format: plain text with clear section headers.

```
=== CHARACTER SHEET ===
Name: Varek
Concept: Changeling Witch
Attributes: Might -1 | Finesse +1 | Wits +2 | Will +1 | Presence 0 | Shadow +2
Abilities: Witchsight (novice), Shapeshifter (adept), Staff Fighting (novice)
State: HP 10/10 | Corruption (Temp) 0/5 | Corruption (Perm) 1
Conditions: none
Equipment: staff, dark cloak, raven familiar (Morn)
```

Only include fields the pack defines. Formatting template is pack-agnostic (just iterate the sheet schema).

#### 1.2 Dice rolling

Slash commands:

- `/rollattr <attribute_key>` — rolls 2d6, adds attribute value from sheet, injects formatted result as OOC message
- `/pbtaroll <modifier>` — ad-hoc 2d6+mod
- `/rollability <ability_name>` — looks up ability in sheet, uses its category's `roll_attribute` from pack, applies any modifier, injects result AND flags that the ability was activated (so canon/resource modules can react)

Output format injected into chat:

```
[ROLL: Wits check — 2d6 (4+5=9) + 2 = **11 — full success**]
```

Result band interpretation:
- 10+: full success
- 7-9: partial success
- 2-6: failure with consequences

The extension does not adjudicate consequences — it just injects the roll. The GM narrates.

**Quick Reply integration**: the extension registers one Quick Reply button per attribute, dynamically named from the pack. If the pack is reloaded with different attribute names, the Quick Replies update.

#### 1.3 Backup and restore bundle

Slash commands:

- `/backup-export` — produces a ZIP bundle, triggers browser download
- `/backup-import` — opens a file picker, validates the bundle, restores state (destructive — requires confirmation)

**Bundle structure** (inside the ZIP):

```
manifest.json                   # version info, timestamp, campaign name, checksums
chat.jsonl                      # full chat log in SillyTavern's native format
lorebook.json                   # complete active lorebook
authors_note.txt                # current AN
character_sheet.json            # extension's stored sheet
extension_settings.json         # full extension configuration
summary.txt                     # current Summarize extension output
vector_store_export.json        # vector storage export if feasible; else empty with flag
pack_reference.json             # pack_name and version used
README.txt                      # auto-generated explanation
```

Filename convention: `campaign_<slug>_<YYYYMMDD_HHMMSS>.zip` where `<slug>` is derived from the chat name.

Settings option: auto-export on `/scene-end`, on session end (how? detect inactivity timer), or never.

**Import flow:**
1. User runs `/backup-import`, picks a file
2. Extension validates manifest: SillyTavern version compatibility, extension version compatibility, checksums
3. If version mismatches: warn clearly, require explicit override confirmation
4. Destructive confirmation modal: "This will replace current chat, lorebook, AN, and sheet. Proceed?"
5. Atomically replace state. If any step fails, roll back.

**Vector storage caveat:** SillyTavern's vector storage may not expose clean export/import. Fallback: if export fails, store a `rebuild_from_chat: true` flag in the bundle; on import, re-embed from chat after restore. Slower but correct. Document this behavior.

---

### Tier 2 — Build after first playtest

#### 2.1 STATUS_UPDATE parser

After each GM message (`MESSAGE_RECEIVED` event), scan for:

```
[STATUS_UPDATE]
hp_current: 10 -> 7
conditions: +bleeding
corruption_temporary: 0 -> 1
inventory: -torch, +silver dagger
[/STATUS_UPDATE]
```

Parse the block into a diff against the current sheet. Field names must match pack-defined resource keys (use the pack's whitelist). Unknown fields are flagged, not silently dropped.

Show a non-blocking modal: "GM proposes these changes: [list]. Accept / Edit / Ignore?"

On accept: apply deltas atomically. If a threshold is crossed (e.g., `corruption_temporary` reaches `corruption_threshold`), apply the pack-declared consequence (`threshold_effect`) and notify the player.

#### 2.2 Author's Note management

The AN has structured sections. The extension parses and writes each independently.

Expected sections (matching `08_EXAMPLE_PACK_SYMBAROUM.md` format):
- Current Act
- Pending beats
- Active threads
- Recent beats
- Reminders

**Operations:**

- **`/scene-end`** — prompts GM to wrap scene, then triggers recent-beats update + status-update parse + optional summarize
- **`/act-transition`** — user-initiated. Reads current-act lorebook entry, advances it per the campaign's plot skeleton (reads from `spoilers/full_campaign.md` if available, else prompts user), updates both the constant lorebook entry AND the AN's Current Act section
- **Recent beats auto-update** — triggered on scene-end or every N messages (configurable). Reads last K messages, calls LLM to distill 2-3 bullet points. Presents diff view. User accepts or edits.
- **Active threads update** — lower-confidence. Extension proposes thread additions and retirements based on recent messages. Always requires user review. Threads are harder to detect — may require LLM call with longer context.
- **Pending beats** — not auto-updated. Advanced only on `/act-transition`.

Never auto-apply any AN update. Always show a diff and require user confirmation.

#### 2.3 Canon detection

After each GM message:

1. Extract proper nouns via regex (capitalized words not at sentence start, filtered against a stopword list)
2. Compare against current lorebook entry keywords
3. For candidates that appear 2+ times in the message or in high-salience contexts (dialogue attribution, possessive, title), flag them
4. For flagged candidates, call LLM: "Given this message, is [entity] a new named NPC / location / faction / item worth adding to the campaign bible? If yes, draft a lorebook entry in the pack's GM-facing style."
5. Show non-blocking modal with drafted entry. User accepts, edits, or ignores.
6. On accept: write to active lorebook via World Info API.

Same LLM provider as SillyTavern's main chat; no separate credentials.

Cooldown: after a user ignores a proposed entry, the extension should not re-propose the same entity for N messages (prevent nagging).

---

### Tier 3 — Build as pain emerges

#### 3.1 Scene transition helper

Already covered by `/scene-end` above — this is just the button/Quick Reply wrapper.

#### 3.2 Lorebook hygiene

Periodic or on-demand maintenance dashboard:

- Entries not fired in last N messages (stale)
- Keyword collisions (two entries firing on same word)
- Oversize entries (token count over threshold)
- Orphan entries (not connected to current act or active threads)

Surface as a dashboard; never auto-fix.

#### 3.3 Session log export

`/session-export` — produces a markdown file with:
- Session summary
- Full chat log (formatted)
- List of lorebook entries added this session
- Final character sheet state

Downloads to user's machine. Different from backup bundle: this is human-readable, for review/sharing, not for restore.

#### 3.4 Pack switcher UI

Settings panel: dropdown showing available packs in the configured pack directory. Switching pack requires confirmation (clears sheet if schema-incompatible). Used for starting a new campaign in a different genre.

---

## Design principles

1. **Suggest, don't automate.** Every state change requires confirmation. Silent automation on creative state is how campaigns corrupt unnoticed.
2. **Pack-driven.** Attributes, resources, abilities come from the pack. No hardcoded names.
3. **Graceful degradation.** If LLM call fails, feature no-ops quietly.
4. **Configurable.** All thresholds and cadences in the settings panel.
5. **Transparent.** Log view shows what the extension did, when, and why.
6. **Reversible.** Every write has an undo.

---

## Project layout

```
solo-ttrpg-assistant/
├── manifest.json
├── README.md
├── CHANGELOG.md
├── TESTING.md
├── index.js                    # entry, event wiring, slash command registration
├── settings.js                 # settings panel
├── modules/
│   ├── pack.js                 # pack loading and schema access
│   ├── sheet.js                # character sheet state + UI
│   ├── dice.js                 # roll commands + Quick Reply registration
│   ├── backup.js               # export/import bundle
│   ├── status_update.js        # STATUS_UPDATE parser
│   ├── authors_note.js         # AN section management
│   ├── canon_detection.js      # proper noun extraction + lorebook proposals
│   ├── act_transition.js       # act advancement
│   ├── lorebook_hygiene.js     # dashboard
│   ├── session_export.js       # markdown export
│   └── logger.js               # unified activity log
├── ui/
│   ├── sheet_panel.html
│   ├── sheet_panel.css
│   ├── confirm_modal.html
│   ├── diff_view.html
│   ├── settings_panel.html
│   └── log_view.html
└── lib/
    ├── yaml.js                 # for reading pack YAML files
    ├── zip.js                  # for backup bundle
    └── diff.js                 # for diff views
```

---

## Testing

Manual test checklist in `TESTING.md`:

- Load extension in a dev SillyTavern instance
- **Pack loading:** click "Load pack" in settings, pick the example Symbaroum directory from `08_EXAMPLE_PACK_SYMBAROUM.md` rendered as a real directory. Verify pack loads, confirmation shows correct display_name and version.
- **Pack persistence:** reload SillyTavern, verify the pack is still loaded without re-picking
- **Degraded mode:** on a fresh install with no pack loaded, verify the extension doesn't crash and the sheet renders in minimal mode
- **Multiple packs:** load a second pack directory, verify both appear in the pack dropdown, verify switching between them updates dice command names and sheet UI
- **Compatibility check:** open a chat whose `__pack_reference` names a different pack than is currently active, verify the warning modal appears
- **Malformed pack:** remove a required file from a pack directory, attempt load, verify specific error message naming the missing file; verify no partial load occurred
- **Reload:** edit a pack file on disk, click "Reload pack", verify changes propagate to the extension's in-memory state
- Create a character, exercise all sheet fields
- Roll every attribute via Quick Reply and slash command
- Run `/backup-export`, verify ZIP contents include `__pack_reference` in the lorebook
- `/backup-import` into a fresh chat, verify state matches and compatibility check fires if pack is not loaded
- Send a GM message with a STATUS_UPDATE block, verify parse + modal; verify the field whitelist from `resources.yaml` is enforced
- Send a GM message with a new NPC, verify canon detection proposal
- Run `/scene-end`, verify AN diff view
- Run `/act-transition`, verify both lorebook and AN update
- Stress-test with 200+ message chat, check performance

---

## Verification before declaring done

- [ ] Tier 1 features (sheet, dice, backup) fully functional and tested
- [ ] Loads and respects the example Symbaroum pack
- [ ] Backup/restore round-trip preserves chat, lorebook, AN, sheet verbatim
- [ ] Pack switching works without corrupting state (prompts user when schemas differ)
- [ ] No silent state changes — every write traceable in the log view
- [ ] Graceful degradation when LLM calls fail
- [ ] Documentation includes screenshots and a quick-start guide
