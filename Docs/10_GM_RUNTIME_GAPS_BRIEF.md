# GM Runtime Gaps — Plan Brief

This brief covers three features identified during the SillyTavern campaign-runtime audit ([campaign_7 review](../campaign_generator/campaigns/my_first_campaign_7/)) as **missing-but-valuable**. They are out of scope for the bug-fix pass that landed in [03_CAMPAIGN_GENERATOR_BRIEF.md](03_CAMPAIGN_GENERATOR_BRIEF.md), and are tracked here as a separate workstream.

The audit found that the generated lorebook is structurally valid and content-rich, but a GM running an actual session is missing three categories of always-on operational support. Each feature below is a self-contained addition that emits one or more new World Info entries (or modifies the assembly path) without changing the existing stages.

---

## Context — what the runtime currently provides

A campaign run from `campaign_generator` produces a SillyTavern World Info JSON containing:
- `GM Prompt Overlay` — pack-derived genre-flavored GM instructions (constant, always injected)
- `Failure Moves` — pack-derived list of consequences for failed rolls (constant)
- `Campaign Bible` — premise + tone + themes (constant)
- `Current Act` — Act 1 goals and beats (constant)
- Per-NPC, per-location, per-faction, per-clue entries (keyword-triggered)
- Per-NPC `NPC Secret` entries (disabled by default; GM unlocks per reveal)
- Branch contingencies entry (keyword-triggered)
- `opening_hook.txt`, `initial_authors_note.txt`, `spoilers/full_campaign.md`

What's missing for someone actually trying to GM with this:

1. **No session-zero / character-creation guidance entry** — `opening_hook.txt` lists three generic guidance bullets, but there is no World Info entry the GM can lean on during the table conversation that builds the party, nor any structured prompt for the LLM to facilitate that conversation.
2. **No reusable scene templates** — investigation scenes, corruption manifestations, and faction-pressure scenes recur across the campaign, but the GM (and the LLM acting as GM) has no scaffold to reach for. Each scene is improvised cold from the bible + current-act entry.
3. **No fallback-hook coverage** — if the players ignore the mentor's storyline or refuse to engage with the Valerius family, there is no documented redirect. The clue graph wires beats to clues, but there is no "if the table has stalled for 20 minutes, do this" entry.

These are not bugs in the generator. They are content categories the design has not yet asked for.

---

## Feature 1 — Session-Zero / Character-Creation Entry

### Problem

`opening_hook.txt` ships three boilerplate character-creation bullets that don't reflect the campaign's specific factions, locations, or hooks. A GM running session zero — the table conversation where players make characters — needs richer, campaign-specific scaffolding:

- which factions a PC could plausibly belong to (with the trust/cost implications of each)
- what kinds of expertise the table needs to cover (investigation, social, combat, ritual)
- which opening-scene roles are available (mentor's apprentice, hired investigator, faction agent, frontier survivor)
- what the campaign's "central question" is, framed for player buy-in

### Approach

Add a new pipeline stage `12. session_zero` that runs **after** `npcs`, `factions`, and `opening_hook`, and produces a single structured document. Emit it as:

- A new file `session_zero.txt` at the campaign root, alongside `opening_hook.txt`. This is the human-facing artifact the GM reads aloud or paraphrases at the table.
- A new World Info entry `Session Zero Guidance`, `constant: false`, keyed on `["session zero", "character creation", "session 0", "make a character"]` with `selective: true`. This lets the LLM-GM pull it up if a player asks "what kind of character should I make?" mid-prep.

### Schema

New pydantic model in [schemas.py](../campaign_generator/campaign_generator/schemas.py):

```python
class SessionZeroDocument(BaseModel):
    central_question: str                          # one-line buy-in framing
    party_composition_needs: list[str]             # 3-5 expertise bullets
    faction_membership_options: list[FactionPick]  # per-faction trust/cost summary
    opening_scene_roles: list[OpeningRole]         # 3-5 entry-point archetypes
    table_agreements: list[str]                    # safety/tone agreements (lines/veils)
    first_session_anchor: str                      # what the first scene asks of the party
```

Where `FactionPick` cites a real faction by canonical name (validated against `FactionSet`) and `OpeningRole` cites a relevant NPC or location by canonical name (validated against `NPCRoster` / `LocationCatalog`). Cross-stage validation enforces this — same pattern as existing checks in [validation.py](../campaign_generator/campaign_generator/validation.py).

### Files

- [campaign_generator/stages/session_zero.py](../campaign_generator/campaign_generator/stages/session_zero.py) — new
- [prompts/12_session_zero.md](../campaign_generator/prompts/12_session_zero.md) — new, schema-bound
- [campaign_generator/schemas.py](../campaign_generator/campaign_generator/schemas.py) — add `SessionZeroDocument`
- [campaign_generator/pipeline.py](../campaign_generator/campaign_generator/pipeline.py) — add stage, write `session_zero.txt`
- [campaign_generator/lorebook.py](../campaign_generator/campaign_generator/lorebook.py) — emit the `Session Zero Guidance` entry
- [tests/fixtures/canned_llm_responses/session_zero.json](../campaign_generator/tests/fixtures/canned_llm_responses/session_zero.json) — new fixture

### Verification

- Unit test: schema validates a hand-crafted fixture; cross-stage validation rejects a fixture where `faction_membership_options` references a non-roster faction.
- Replay-pipeline test asserts `session_zero.txt` is written.
- Manual: run end-to-end on the Symbaroum seed; review the `session_zero.txt` for table-readiness (does it actually help a GM run the conversation?).

### Out of scope for this feature

- A multi-turn LLM-driven character interview at session zero. This is a runtime feature for the SillyTavern extension, not a generator feature. Tracked separately in [04_EXTENSION_BRIEF.md](04_EXTENSION_BRIEF.md) if/when added.

---

## Feature 2 — Reusable Scene Templates

### Problem

The same scene shapes recur across a campaign — an investigation, a faction-pressure encounter, a corruption manifestation, a downtime/recovery scene. The LLM-GM currently has to improvise the structure of each one cold from the bible + current-act entry, which produces inconsistent pacing and skipped beats.

A small set of **scene templates** as constant or keyword-triggered entries would give the LLM a scaffold to fill in: "when running an investigation, work through these stages; when running a corruption manifestation, escalate sensory detail in this order".

### Approach

Two-layer design:

1. **Pack-level scene templates** — generic, genre-flavored scaffolds owned by the genre pack. New pack file `scene_templates.md` ([02_GENRE_PACK_SPEC.md](02_GENRE_PACK_SPEC.md) gets a section). The Symbaroum pack ships templates for: **Investigation Sequence**, **Corruption Manifestation**, **Faction Pressure**, **Ritual Attempt**, **Downtime Reckoning**. Other packs ship their own. Each template is a few hundred words: trigger conditions, scene phases, escalation cues, exit options.

2. **Campaign-level scene anchors** — the generator produces a per-campaign `scene_index` document (3-6 scenes) that names *which template applies where in the plot*, e.g. "Act 2 beat 3 is best run as an Investigation Sequence anchored at the Sunken Watchtower; corruption manifestation triggers if the party fails the ritual roll in Act 3 beat 1". This pins the abstract templates to the concrete plot.

### Lorebook emission

- One World Info entry per pack template, `constant: false`, keyed on the template name and a couple of common synonyms (`["investigation", "investigate", "search the scene"]` for the Investigation Sequence template). The LLM-GM pulls them up when the players signal an investigation phase.
- One `Scene Anchors` entry, keyed on the act/beat labels (`["1.1", "act 1 beat 1", "Act 1"]`), content lists which template applies to which beat. This is `selective: true` and is order-adjacent to the per-act entries.

### Files

- [02_GENRE_PACK_SPEC.md](02_GENRE_PACK_SPEC.md) — add `scene_templates.md` to the required pack files list
- [genres/symbaroum_dark_fantasy/scene_templates.md](../genres/symbaroum_dark_fantasy/scene_templates.md) — new, ships with example templates
- [campaign_generator/pack.py](../campaign_generator/campaign_generator/pack.py) — load `scene_templates.md` into the `GenrePack` model
- [campaign_generator/stages/scene_anchors.py](../campaign_generator/campaign_generator/stages/scene_anchors.py) — new stage, runs after `clue_chains`, produces a `SceneAnchorPlan`
- [prompts/13_scene_anchors.md](../campaign_generator/prompts/13_scene_anchors.md) — new
- [campaign_generator/lorebook.py](../campaign_generator/campaign_generator/lorebook.py) — emit per-template entries and the `Scene Anchors` entry
- [tests/test_pack_validation.py](../campaign_generator/tests/test_pack_validation.py) — assert pack ships scene_templates
- [tests/fixtures/canned_llm_responses/scene_anchors.json](../campaign_generator/tests/fixtures/canned_llm_responses/scene_anchors.json) — new fixture

### Schema

```python
class SceneAnchor(BaseModel):
    beat_id: str           # canonical, validated against PlotSkeleton
    template_name: str     # validated against pack.scene_template_names
    notes: str             # 1-2 sentence campaign-specific tweak

class SceneAnchorPlan(BaseModel):
    anchors: list[SceneAnchor] = Field(min_length=3, max_length=8)
```

Cross-stage validation: every `template_name` resolves to a real template; every `beat_id` resolves to a canonical beat.

### Verification

- Pack-load test confirms `scene_templates.md` is parsed and template names extracted.
- Pipeline test asserts the lorebook contains one entry per template plus a `Scene Anchors` entry.
- Manual: run the Symbaroum seed end-to-end and verify the scene anchors actually map sensible templates to plausible beats.

### Out of scope

- Auto-running the scene template (extension-level concern). The generator just makes the scaffolds available.

---

## Feature 3 — Fallback Hooks for Player Disengagement

### Problem

If the players ignore the mentor storyline, refuse to engage with the Valerius family, or simply stall for 20 minutes in a roleplay tangent, the LLM-GM has no documented "redirect lever" to pull. The clue graph wires beats to clues but has no concept of "what if the players never look for clues?".

A campaign should ship a small set of **escalation pressures** — events the GM can introduce to advance the world-state when the party stalls. A faction makes a move, an NPC acts on their motivation, a corruption tick lands. These are not "railroad nudges"; they are world-events that exist regardless of player attention.

### Approach

Add a stage `14. pressure_events` that runs **after** `branches` and produces 4-7 timed pressure events, each with:

- A trigger condition (`"if no clue from Act 2 has been found by the third in-fiction night"`, `"if the party has not visited Thistle Hold in 2 sessions"`)
- A world-event that fires (`"Lord Cassius Valerius dispatches a search party — which the players will hear about by morning"`)
- An escalation outcome (`"this advances Act 2 beat 3 even if the players didn't earn it"`)

These are emitted as one keyword-triggered World Info entry per event (keyed on the relevant faction/NPC/location names so the LLM picks them up when the players talk about that subject) plus a constant `Pressure Index` entry that lists all of them with their trigger conditions.

### Schema

```python
class PressureEvent(BaseModel):
    name: str
    trigger_condition: str          # human-readable; not machine-evaluated
    world_event: str                # 1-2 sentences of what happens
    escalation_outcome: str         # which beat/branch this advances
    references: list[str]           # NPC/faction/location names; cross-validated

class PressureEventPlan(BaseModel):
    events: list[PressureEvent] = Field(min_length=4, max_length=8)
```

Cross-stage validation: `references` must resolve via the same token map already used by `branches` ([stages/branches.py](../campaign_generator/campaign_generator/stages/branches.py)).

### Files

- [campaign_generator/stages/pressure_events.py](../campaign_generator/campaign_generator/stages/pressure_events.py) — new
- [prompts/14_pressure_events.md](../campaign_generator/prompts/14_pressure_events.md) — new
- [campaign_generator/schemas.py](../campaign_generator/campaign_generator/schemas.py) — add `PressureEvent`, `PressureEventPlan`
- [campaign_generator/pipeline.py](../campaign_generator/campaign_generator/pipeline.py) — add stage
- [campaign_generator/lorebook.py](../campaign_generator/campaign_generator/lorebook.py) — emit per-event entries + `Pressure Index`
- [campaign_generator/stages/spoilers.py](../campaign_generator/campaign_generator/stages/spoilers.py) — include pressure events in `full_campaign.md`
- [tests/fixtures/canned_llm_responses/pressure_events.json](../campaign_generator/tests/fixtures/canned_llm_responses/pressure_events.json) — new fixture

### Lorebook entry shape

- Per-event entry: `comment: "Pressure: <name>"`, keys are the references, `constant: false`, `selective: true`, `order: 250` (between clues and locations). Content includes the trigger condition, world event, and escalation outcome.
- `Pressure Index` entry: `constant: false`, keyed on `["pressure", "stalled", "what now", "they won't engage"]`, content lists all events with one-line summaries. The LLM-GM looks here when the table has lost momentum.

### Verification

- Pipeline replay test asserts the lorebook contains pressure-event entries and a `Pressure Index`.
- Cross-stage test asserts a pressure event with an unknown faction reference triggers a validation error.
- Manual: run the Symbaroum seed end-to-end; review whether the pressure events provide useful redirect levers without feeling railroad-y.

### Out of scope

- Automatic firing of pressure events based on chat-time elapsed. That would be an extension feature.

---

## Sequencing & dependencies

These three features are **independent** and can be built in any order. The recommended order:

1. **Feature 2 first** (scene templates) — it touches the genre pack spec, which is the most invasive change. Doing it first lets the pack generator team weigh in once. Also produces the most immediate GM uplift per token of work.
2. **Feature 3 second** (pressure events) — small, self-contained, reuses the existing branch token-validation. Lowest risk.
3. **Feature 1 last** (session zero) — depends on having factions, NPCs, locations, and ideally pressure events available so the session-zero document can reference all of them coherently.

Each feature is roughly the size of an existing pipeline stage (~1 prompt file, ~1 stage module, ~1 schema, ~1 fixture, lorebook integration, tests). All three should land independently with their own PRs.

---

## Verification checklist for the workstream

- [ ] Each feature ships independently behind its own PR
- [ ] Each feature adds at least one fixture-driven replay test
- [ ] Each feature's lorebook entries are byte-stable across regeneration of the same seed (no drift on identical inputs)
- [ ] Cross-stage validation rejects invalid references for each new entity type
- [ ] All three features pass through the SillyTavern import smoke test (lorebook loads cleanly, entries fire on expected keywords)
- [ ] [03_CAMPAIGN_GENERATOR_BRIEF.md](03_CAMPAIGN_GENERATOR_BRIEF.md) is updated to document each new stage and its lorebook output
- [ ] The Symbaroum example pack is updated to demonstrate the new artifacts (especially `scene_templates.md`)
