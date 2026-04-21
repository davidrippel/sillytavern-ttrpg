You write only valid JSON matching the requested schema.

Task: produce an explicit clue graph, not prose.

Requirements:
- stay close to `target_clue_count`; do not explode into dozens or hundreds of clues
- every clue has a unique id
- `found_at_type` must be only `npc` or `location`
- `found_at` must be copied exactly from the supplied NPC or location menus
- for beats, use only beat ids from the supplied `beat_menu`
- all references must point to existing clues, NPCs, locations, or act beats
- ensure investigation redundancy and no dead ends
- never invent extra NPCs, locations, beat ids, or special found_at types like `hook`, `item`, or `starting_clue`
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name
