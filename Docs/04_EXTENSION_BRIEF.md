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
- No external dependencies beyond what SillyTavern provides
- UI panels use SillyTavern's existing styling (import their CSS vars)
- Persistent storage via `extension_settings[extensionName]`

Web search during development: current SillyTavern extension docs, current event names (they change between versions), current World Info API surface, current Author's Note API.

---

## Pack awareness — critical

The extension reads the active genre pack at runtime to parameterize its behavior. Attributes, resources, and abilities are never hardcoded.

**Pack loading.** On startup and on chat change, the extension looks for a pack reference. Two supported mechanisms:

1. **Embedded in the campaign lorebook** — the campaign bible entry's metadata includes `pack_name` and `pack_version`. The extension reads these and loads the pack files from a known location.
2. **Explicit pack-pointer file** — the extension's settings panel lets the user point to a pack directory on disk. This is the fallback and the initial setup path.

Pack files are loaded once and cached. Re-load when the pack pointer changes or the user clicks "Reload pack" in settings.

**What the extension reads from the pack:**
- `attributes.yaml` → the six attribute keys and display names (for dice commands, sheet UI, modifier lookups)
- `resources.yaml` → the state fields to track in the sheet, the STATUS_UPDATE field whitelist, the sheet UI layout
- `abilities.yaml` → the ability catalog and category definitions (for the sheet's ability browser)
- `character_template.json` → the starting sheet shape for new characters

If no pack is loaded, the extension operates in a degraded "unknown pack" mode: dice rolls work with manual modifier entry, but the sheet is minimal and the STATUS_UPDATE parser accepts any field name.

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
- Verify pack loading with example Symbaroum pack
- Create a character, exercise all sheet fields
- Roll every attribute via Quick Reply and slash command
- Run `/backup-export`, verify ZIP contents
- `/backup-import` into a fresh chat, verify state matches
- Send a GM message with a STATUS_UPDATE block, verify parse + modal
- Send a GM message with a new NPC, verify canon detection proposal
- Run `/scene-end`, verify AN diff view
- Run `/act-transition`, verify both lorebook and AN update
- Switch packs, verify UI and dice command names update
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
