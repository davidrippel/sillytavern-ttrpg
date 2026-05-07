You write only valid JSON matching the requested schema.

Task: create campaign contingencies that respond to major player choices.

Requirements:
- 6-10 branches
- each branch follows an if-then form
- later-act consequences must be explicit
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name
- in `if_condition`, `then_outcome`, and `later_act_consequences`, ONLY mention NPCs, factions, and locations that are present in the supplied `npcs`, `factions`, and `locations` arrays. Do NOT invent new named characters in the prose; if you need an additional figure, refer to them by role (e.g. "the rival journalist") rather than inventing a name.

The `references` field — read carefully:

- Each entry in `references` MUST be a verbatim token from the supplied `reference_menu`. The validator rejects any entry that isn't in the menu, and the campaign fails to generate.
- Valid tokens look like: `act1_beat3`, `act2_beat2`, an NPC's exact name (e.g. `"Morris Katz"`), a faction's exact name (e.g. `"The Whisper Network"`), a location's exact name, or a clue id (e.g. `"repair_clue03a"`).
- Do NOT put paraphrased plot beats, sentence fragments, ellipsis-trailing summaries (`"Elara confronts the protagonist..."`), or invented identifiers in `references`. Those belong in the prose fields, not in `references`.
- If a branch's prose talks about an event but no menu token captures it, omit that reference rather than inventing one.
