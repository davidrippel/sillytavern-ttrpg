You write only valid JSON matching the requested schema.

Task: rewrite a single clue's `reveals` text as evocative, in-fiction prose. You do NOT change the clue's structure — `id`, `found_at_type`, `found_at`, `points_to`, and `supports_beats` are fixed and must be returned exactly as supplied. Only the `reveals` field changes.

Requirements:
- write 1–3 sentences that a GM could read aloud or paraphrase in play
- ground the prose in the supplied `found_at` (the NPC or location where the clue is discovered)
- make the clue feel like discoverable evidence, dialogue, or sensory detail — not a plot summary
- reference the supplied `beat_context` so the clue clearly points the players forward
- do not invent NPCs, locations, beat ids, or factions that aren't in the supplied context
- whenever referring to the player character, use the exact placeholder `{{user}}` and never invent a protagonist name
- preserve all structural fields verbatim from the input
