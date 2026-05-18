You are writing the default campaign seed for a TTRPG genre pack. This file is loaded by the campaign generator when the user runs it without supplying their own seed. The runtime is story-mode only — there are no acts, no beats, no clue chains. Do NOT emit `num_acts`, `clue_chain_density`, or `branch_points`; the validator rejects packs that carry them.

You will receive: tone/pillars, the GM overlay's setting_and_tone and npc_conventions sections, and the brief.

Produce JSON:

- `setting_anchors`: 4-6 specific named places, locales, or institutions the campaign generator should anchor on. SPECIFIC — `derelict_colonies, alien_ruins, contested_trade_routes` beats `the_frontier`. snake_case. Each anchor must be at least two tokens long and not in the cliché blocklist (`the_frontier`, `the_void`, `the_belt`, etc.).
- `themes_include`: 4-6 thematic threads the generator should weave in. snake_case.
- `themes_exclude`: 2-4 themes the generator should not touch. snake_case. Must not overlap or contradict `themes_include` or `tone`.
- `tone`: 3-5 tone keywords for the campaign. snake_case.
- `antagonist_archetypes_preferred`: 3-6 antagonist types the generator should draw from. snake_case. At least 3 distinct.
- `num_npcs`: integer, range 8-30. Typical 15-20 for a campaign with a substantial faction landscape; 10-12 for a tighter mystery.
- `num_locations`: integer, range 6-20. Typical 10-12.
- `num_factions`: integer, range 2-6. Typical 3-4.
- `num_truths`: integer, range 5-10. How many atomic underlying truths the campaign hangs on (the "answer key" the campaign generator's truths stage will produce). Fewer truths = tighter mystery; more truths = sprawling campaign.
- `num_complications`: integer, range 8-15. How many CAMPAIGN-SPECIFIC complications the generator layers on top of the pack's universal complications list.

Be specific everywhere. The campaign generator instantiates against these defaults — vague anchors produce a vague campaign.

Return JSON only.
