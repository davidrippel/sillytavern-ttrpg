You write only valid JSON matching the requested schema.

Task: design the **final node** of this act — the dramatic culmination the player must reach to advance the campaign.

Context provided:
- `act_start_node`: the act's opening scene (the player begins here).
- `previous_acts_finals`: how previous acts ended. The current act's final must escalate from these.
- `is_campaign_climax`: if true, this is the very last node of the campaign — the victory/climax. Otherwise this final node also acts as the start of the next act.
- For acts 2+: you also receive `npc_roster` and `location_catalog` — you must pick this act's relevant NPCs and locations as part of this prompt.

Your job:

1. **For acts 2+ only** (when `npc_roster` and `location_catalog` are present):
   - Pick **3 to 7 NPCs** from the roster relevant to this act.
   - Pick **2 to 5 locations** from the catalog relevant to this act.
   - Use names EXACTLY as supplied.

2. **Design the final node**:
   - `kind`: `location` / `npc_encounter` / `event`.
   - `description`: 1–3 sentences (20–400 chars). This is the act's dramatic climax — the moment of confrontation, revelation, or decisive choice that ends the act. If `is_campaign_climax` is true, it must feel like the end of the whole campaign.
   - `relevant_npcs`: the NPCs present at this node (subset of the act's selection; typically 1–4).
   - `relevant_location`: the primary location (from the act's selection).

Rules:
- The final node must be the act's **culmination**, not a midpoint. It should feel like reaching it ends the act.
- It must build on `act_start_node`'s premise and escalate from `previous_acts_finals`.
- Whenever referring to the player character, use the exact placeholder `{{user}}`. Never invent a name.
- All NPC and location names must be from the supplied rosters.
- The `beats_as_texture` field is backstory texture — use it to understand the act's tone, not as a sequence to follow.
